data "archive_file" "webhook_lambda" {
  count       = var.enable_webhook_service ? 1 : 0
  type        = "zip"
  source_dir  = "${path.module}/../../lambda_src"
  output_path = "${path.module}/.terraform/${local.name}-webhook-lambda.zip"
}

data "aws_iam_policy_document" "lambda_webhook_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_webhook" {
  count              = var.enable_webhook_service ? 1 : 0
  name               = "${local.name}-lambda-webhook"
  assume_role_policy = data.aws_iam_policy_document.lambda_webhook_assume_role.json
  tags               = local.tags
}

data "aws_iam_policy_document" "lambda_webhook" {
  count = var.enable_webhook_service ? 1 : 0

  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["${aws_cloudwatch_log_group.lambda_webhook[0].arn}:*"]
  }

  statement {
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret"
    ]
    resources = [aws_secretsmanager_secret.webhook_verify_token.arn]
  }

  statement {
    actions = ["ecs:RunTask"]
    resources = [
      "arn:aws:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:task-definition/${aws_ecs_task_definition.worker.family}:*"
    ]

    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [aws_ecs_cluster.main.arn]
    }
  }

  statement {
    actions = ["iam:PassRole"]
    resources = [
      aws_iam_role.ecs_execution.arn,
      aws_iam_role.worker.arn
    ]
  }
}

resource "aws_iam_role_policy" "lambda_webhook" {
  count  = var.enable_webhook_service ? 1 : 0
  role   = aws_iam_role.lambda_webhook[0].id
  policy = data.aws_iam_policy_document.lambda_webhook[0].json
}

resource "aws_cloudwatch_log_group" "lambda_webhook" {
  count             = var.enable_webhook_service ? 1 : 0
  name              = "/aws/lambda/${local.name}-webhook"
  retention_in_days = var.log_retention_days
  tags              = local.tags
}

resource "aws_lambda_function" "webhook" {
  count            = var.enable_webhook_service ? 1 : 0
  function_name    = "${local.name}-webhook"
  role             = aws_iam_role.lambda_webhook[0].arn
  handler          = "webhook_handler.lambda_handler"
  runtime          = "python3.11"
  filename         = data.archive_file.webhook_lambda[0].output_path
  source_code_hash = data.archive_file.webhook_lambda[0].output_base64sha256
  timeout          = 15

  environment {
    variables = local.webhook_lambda_env
  }

  depends_on = [aws_cloudwatch_log_group.lambda_webhook]
  tags       = local.tags
}

resource "aws_apigatewayv2_api" "webhook" {
  count         = var.enable_webhook_service ? 1 : 0
  name          = "${local.name}-webhook"
  protocol_type = "HTTP"
  tags          = local.tags
}

resource "aws_apigatewayv2_integration" "webhook" {
  count                  = var.enable_webhook_service ? 1 : 0
  api_id                 = aws_apigatewayv2_api.webhook[0].id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.webhook[0].invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "webhook_get" {
  count     = var.enable_webhook_service ? 1 : 0
  api_id    = aws_apigatewayv2_api.webhook[0].id
  route_key = "GET /webhook"
  target    = "integrations/${aws_apigatewayv2_integration.webhook[0].id}"
}

resource "aws_apigatewayv2_route" "webhook_post" {
  count     = var.enable_webhook_service ? 1 : 0
  api_id    = aws_apigatewayv2_api.webhook[0].id
  route_key = "POST /webhook"
  target    = "integrations/${aws_apigatewayv2_integration.webhook[0].id}"
}

resource "aws_apigatewayv2_stage" "webhook" {
  count       = var.enable_webhook_service ? 1 : 0
  api_id      = aws_apigatewayv2_api.webhook[0].id
  name        = "$default"
  auto_deploy = true
  tags        = local.tags
}

resource "aws_lambda_permission" "webhook_api_gateway" {
  count         = var.enable_webhook_service ? 1 : 0
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.webhook[0].function_name
  principal     = "apigateway.amazonaws.com"
  # Keep this API-scoped but broad enough for HTTP API route ARN matching on the
  # $default stage. A narrower pattern can prevent API Gateway from invoking the
  # function and produce "not verifiable" webhook registration failures.
  source_arn = "${aws_apigatewayv2_api.webhook[0].execution_arn}/*/*/*"
}

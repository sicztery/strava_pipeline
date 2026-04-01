locals {
  name = var.project_name

  tags = merge(
    var.tags,
    {
      project = var.project_name
    }
  )

  secret_names = {
    client_id     = "${var.secret_prefix}-client-id"
    client_secret = "${var.secret_prefix}-client-secret"
    auth_state    = "${var.secret_prefix}-auth-state"
    webhook_verify_token = "${var.secret_prefix}-webhook-verify-token"
  }

  container_image = var.container_image != "" ? var.container_image : "${aws_ecr_repository.app.repository_url}:latest"

  athena_env = var.pipeline_query_engine == "athena" ? {
    ATHENA_DATABASE        = var.athena_database
    ATHENA_OUTPUT_S3       = var.athena_output_s3
    ATHENA_WORKGROUP       = var.athena_workgroup
    ATHENA_TIMEOUT_SECONDS = tostring(var.athena_timeout_seconds)
    PIPELINE_SQL_PATH      = var.pipeline_sql_path
  } : {}

  container_env = merge(
    {
      BUCKET_NAME           = var.bucket_name
      AWS_REGION            = var.aws_region
      PIPELINE_QUERY_ENGINE = var.pipeline_query_engine
      SECRET_PREFIX         = var.secret_prefix
    },
    { for k, v in local.athena_env : k => v if v != "" },
    var.app_env
  )

  webhook_lambda_env = {
    ECS_CLUSTER                 = aws_ecs_cluster.main.name
    ECS_TASK_DEFINITION         = aws_ecs_task_definition.worker.arn
    ECS_SUBNETS                 = join(",", var.public_subnet_ids)
    ECS_SECURITY_GROUPS         = aws_security_group.worker.id
    ECS_ASSIGN_PUBLIC_IP        = var.assign_public_ip
    ECS_LAUNCH_TYPE             = "FARGATE"
    WEBHOOK_VERIFY_TOKEN_SECRET = local.secret_names.webhook_verify_token
  }

  webhook_callback_url = var.enable_webhook_service ? "${aws_apigatewayv2_api.webhook[0].api_endpoint}/webhook" : ""

  create_subscription_env = merge(
    local.container_env,
    {
      WEBHOOK_VERIFY_TOKEN_SECRET = local.secret_names.webhook_verify_token
    },
    { for k, v in {
        WEBHOOK_CALLBACK_URL = local.webhook_callback_url
      } : k => v if v != "" }
  )
}

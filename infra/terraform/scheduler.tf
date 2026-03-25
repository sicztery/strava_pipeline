data "aws_iam_policy_document" "scheduler_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  count              = var.enable_schedule ? 1 : 0
  name               = "${local.name}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume_role.json
  tags               = local.tags
}

data "aws_iam_policy_document" "scheduler" {
  count = var.enable_schedule ? 1 : 0

  statement {
    actions   = ["ecs:RunTask"]
    resources = ["*"]

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

resource "aws_iam_role_policy" "scheduler" {
  count  = var.enable_schedule ? 1 : 0
  role   = aws_iam_role.scheduler[0].id
  policy = data.aws_iam_policy_document.scheduler[0].json
}

resource "aws_scheduler_schedule" "worker" {
  count = var.enable_schedule ? 1 : 0

  name                         = "${local.name}-worker"
  group_name                   = "default"
  schedule_expression          = var.schedule_expression
  schedule_expression_timezone = "UTC"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_ecs_cluster.main.arn
    role_arn = aws_iam_role.scheduler[0].arn

    ecs_parameters {
      launch_type         = "FARGATE"
      task_definition_arn = aws_ecs_task_definition.worker.arn
      task_count          = 1

      network_configuration {
        subnets          = var.public_subnet_ids
        security_groups  = [aws_security_group.worker.id]
        assign_public_ip = var.assign_public_ip
      }
    }
  }
}

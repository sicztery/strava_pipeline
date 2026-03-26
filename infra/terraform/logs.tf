resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${local.name}-worker"
  retention_in_days = var.log_retention_days
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "webhook" {
  count             = var.enable_webhook_service ? 1 : 0
  name              = "/ecs/${local.name}-webhook"
  retention_in_days = var.log_retention_days
  tags              = local.tags
}

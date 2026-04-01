output "s3_bucket_name" {
  value = aws_s3_bucket.data.bucket
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "worker_task_definition_arn" {
  value = aws_ecs_task_definition.worker.arn
}

output "worker_security_group_id" {
  value = aws_security_group.worker.id
}

output "webhook_api_invoke_url" {
  value       = var.enable_webhook_service ? aws_apigatewayv2_api.webhook[0].api_endpoint : null
  description = "Base invoke URL for the Lambda-backed webhook HTTP API."
}

output "webhook_callback_url" {
  value       = var.enable_webhook_service ? local.webhook_callback_url : null
  description = "Callback URL to register with Strava for the Lambda-backed webhook."
}

output "webhook_lambda_name" {
  value       = var.enable_webhook_service ? aws_lambda_function.webhook[0].function_name : null
  description = "Lambda function name for the webhook ingress."
}

output "create_subscription_task_definition_arn" {
  value       = aws_ecs_task_definition.create_subscription.arn
  description = "Task definition for manual Strava webhook subscription creation."
}

output "scheduler_role_arn" {
  value       = var.enable_schedule ? aws_iam_role.scheduler[0].arn : null
  description = "Only set when enable_schedule is true."
}

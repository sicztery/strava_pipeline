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

output "scheduler_role_arn" {
  value       = var.enable_schedule ? aws_iam_role.scheduler[0].arn : null
  description = "Only set when enable_schedule is true."
}

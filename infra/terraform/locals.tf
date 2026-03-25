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
  }

  container_image = var.container_image != "" ? var.container_image : "${aws_ecr_repository.app.repository_url}:latest"

  container_env = merge(
    {
      BUCKET_NAME           = var.bucket_name
      AWS_REGION            = var.aws_region
      PIPELINE_QUERY_ENGINE = var.pipeline_query_engine
    },
    var.app_env
  )
}

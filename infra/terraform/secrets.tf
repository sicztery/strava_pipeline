resource "aws_secretsmanager_secret" "client_id" {
  name = local.secret_names.client_id
  tags = local.tags
}

resource "aws_secretsmanager_secret" "client_secret" {
  name = local.secret_names.client_secret
  tags = local.tags
}

resource "aws_secretsmanager_secret" "auth_state" {
  name = local.secret_names.auth_state
  tags = local.tags
}

resource "aws_secretsmanager_secret" "webhook_verify_token" {
  name = local.secret_names.webhook_verify_token
  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "client_id" {
  count         = var.bootstrap_secrets ? 1 : 0
  secret_id     = aws_secretsmanager_secret.client_id.id
  secret_string = try(var.secret_values.client_id, "")
}

resource "aws_secretsmanager_secret_version" "client_secret" {
  count         = var.bootstrap_secrets ? 1 : 0
  secret_id     = aws_secretsmanager_secret.client_secret.id
  secret_string = try(var.secret_values.client_secret, "")
}

resource "aws_secretsmanager_secret_version" "auth_state" {
  count         = var.bootstrap_secrets ? 1 : 0
  secret_id     = aws_secretsmanager_secret.auth_state.id
  secret_string = try(var.secret_values.auth_state, "")
}

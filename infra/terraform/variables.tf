variable "aws_region" {
  type = string
}

variable "project_name" {
  type    = string
  default = "strava-pipeline"
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "bucket_name" {
  type = string
}

variable "secret_prefix" {
  type    = string
  default = "strava"
}

variable "bootstrap_secrets" {
  type    = bool
  default = false
}

variable "secret_values" {
  type = object({
    client_id     = string
    client_secret = string
    auth_state    = string
  })
  sensitive = true
  default   = null

  validation {
    condition     = var.bootstrap_secrets == false || var.secret_values != null
    error_message = "When bootstrap_secrets is true, you must provide secret_values."
  }
}

variable "container_image" {
  type    = string
  default = ""
}

variable "task_cpu" {
  type    = number
  default = 256
}

variable "task_memory" {
  type    = number
  default = 512
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "pipeline_query_engine" {
  type    = string
  default = "none"

  validation {
    condition     = contains(["none", "athena"], var.pipeline_query_engine)
    error_message = "pipeline_query_engine must be \"none\" or \"athena\"."
  }
}

variable "athena_database" {
  type    = string
  default = ""

  validation {
    condition     = var.pipeline_query_engine != "athena" || var.athena_database != ""
    error_message = "athena_database is required when pipeline_query_engine is athena."
  }
}

variable "athena_output_s3" {
  type    = string
  default = ""

  validation {
    condition     = var.pipeline_query_engine != "athena" || var.athena_output_s3 != ""
    error_message = "athena_output_s3 is required when pipeline_query_engine is athena."
  }
}

variable "athena_workgroup" {
  type    = string
  default = ""
}

variable "athena_timeout_seconds" {
  type    = number
  default = 300
}

variable "pipeline_sql_path" {
  type    = string
  default = ""
}

variable "app_env" {
  type    = map(string)
  default = {}
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "enable_schedule" {
  type    = bool
  default = false
}

variable "schedule_expression" {
  type    = string
  default = "rate(1 hour)"
}

variable "assign_public_ip" {
  type    = string
  default = "ENABLED"

  validation {
    condition     = contains(["ENABLED", "DISABLED"], var.assign_public_ip)
    error_message = "assign_public_ip must be ENABLED or DISABLED."
  }
}

variable "enable_webhook_service" {
  type    = bool
  default = true
}

variable "webhook_container_port" {
  type    = number
  default = 8080
}

variable "webhook_desired_count" {
  type    = number
  default = 1
}

variable "webhook_cooldown_seconds" {
  type    = number
  default = 180
}

variable "webhook_callback_url" {
  type    = string
  default = ""
}

variable "webhook_certificate_arn" {
  type    = string
  default = ""
}

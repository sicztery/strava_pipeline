# Terraform Deployment for Strava Pipeline

This directory is the canonical and best-supported way to provision the Strava Pipeline on AWS.

The Terraform configuration matches the current application architecture:

- API Gateway HTTP API and Lambda handle public webhook ingress
- ECS Fargate runs the worker and `create_sub` tasks
- S3 stores state, raw files, and staging files
- Secrets Manager stores Strava credentials and webhook verification data
- ECR stores container images
- CloudWatch Logs stores runtime logs
- EventBridge Scheduler can trigger the worker on a schedule
- Athena and Glue are optional and support the SQL materialization step

This stack assumes you already have:

- an AWS account
- a VPC
- public subnets with outbound internet access
- AWS credentials available to Terraform

It does not create the VPC, subnet layout, Route 53 records, or custom domains for you.

## What Terraform Creates

The configuration in this folder provisions:

- one S3 bucket with encryption enabled and public access blocked
- Secrets Manager secrets for:
  - `<secret_prefix>-client-id`
  - `<secret_prefix>-client-secret`
  - `<secret_prefix>-auth-state`
  - `<secret_prefix>-webhook-verify-token`
- one ECR repository for the application image
- one ECS cluster
- one worker task definition that runs `python -m app.main worker`
- one `create_sub` task definition that runs `python -m app.main create_sub`
- one Lambda function for the public webhook ingress
- one API Gateway HTTP API exposing `GET /webhook` and `POST /webhook`
- CloudWatch log groups for the worker and Lambda ingress
- IAM roles and policies for ECS execution, worker runtime, Lambda webhook, and the optional scheduler
- one EventBridge Scheduler schedule when enabled
- one Glue catalog database and two Athena tables when `pipeline_query_engine = "athena"`

## Quick Start

### 1. Create `terraform.tfvars`

Create `infra/terraform/terraform.tfvars` with values for your environment.

Minimal example:

```hcl
aws_region        = "eu-north-1"
project_name      = "strava-pipeline"
vpc_id            = "vpc-xxxxxxxx"
public_subnet_ids = ["subnet-aaaaaaaa", "subnet-bbbbbbbb"]

bucket_name = "my-unique-strava-pipeline-bucket"
secret_prefix = "strava"

enable_webhook_service = true
enable_schedule        = false

pipeline_query_engine = "none"
container_image       = ""
```

Notes:

- `container_image = ""` means Terraform will point ECS at `<ecr_repository_url>:latest`.
- `enable_webhook_service = true` keeps the Lambda-backed public webhook enabled.

### 2. Initialize and review the plan

```bash
terraform init
terraform plan
```

### 3. Apply

```bash
terraform apply
```

### 4. Inspect outputs

```bash
terraform output
```

Important outputs include:

- `ecr_repository_url`
- `ecs_cluster_name`
- `worker_task_definition_arn`
- `worker_security_group_id`
- `webhook_api_invoke_url`
- `webhook_callback_url`
- `webhook_lambda_name`
- `create_subscription_task_definition_arn`
- `scheduler_role_arn`

## Required Inputs

| Variable | Purpose |
|----------|---------|
| `aws_region` | AWS provider region |
| `vpc_id` | Existing VPC for the ECS security group |
| `public_subnet_ids` | Existing public subnets used by ECS tasks |
| `bucket_name` | S3 bucket name for state, raw, and staging data |

## Important Optional Inputs

| Variable | Default | Purpose |
|----------|---------|---------|
| `project_name` | `strava-pipeline` | Base name for AWS resources |
| `secret_prefix` | `strava` | Prefix for Secrets Manager names |
| `container_image` | `""` | Override the image used by ECS |
| `task_cpu` | `256` | CPU for ECS task definitions |
| `task_memory` | `512` | Memory for ECS task definitions |
| `enable_webhook_service` | `true` | Create the Lambda-backed public webhook ingress |
| `enable_schedule` | `false` | Create an EventBridge Scheduler job for the worker |
| `schedule_expression` | `rate(1 hour)` | Scheduler expression in UTC |
| `assign_public_ip` | `ENABLED` | Public IP behavior for ECS tasks |
| `pipeline_query_engine` | `none` | `none` or `athena` |
| `athena_database` | `""` | Required when Athena is enabled |
| `athena_output_s3` | `""` | Required when Athena is enabled |
| `athena_workgroup` | `""` | Optional Athena workgroup |
| `athena_timeout_seconds` | `300` | Athena polling timeout for the worker |
| `pipeline_sql_path` | `""` | Optional override for the SQL file path inside the container |
| `app_env` | `{}` | Extra environment variables passed into application containers |
| `tags` | `{}` | Extra AWS tags |

## Webhook and Runtime Contract

### Webhook ingress

`enable_webhook_service = true` creates:

- a Lambda webhook handler
- an API Gateway HTTP API exposing `GET /webhook` and `POST /webhook`
- a computed callback URL output for Strava registration

The Lambda webhook:

- serves `GET /webhook` for Strava verification
- serves `POST /webhook` for Strava events
- runs `ecs:RunTask` against the worker task definition

### Runtime variables injected by Terraform

Worker containers receive:

- `BUCKET_NAME`
- `AWS_REGION`
- `SECRET_PREFIX`
- `PIPELINE_QUERY_ENGINE`
- optional `ATHENA_*` variables

The Lambda webhook receives:

- `ECS_CLUSTER`
- `ECS_TASK_DEFINITION`
- `ECS_SUBNETS`
- `ECS_SECURITY_GROUPS`
- `ECS_ASSIGN_PUBLIC_IP`
- `ECS_LAUNCH_TYPE`
- `WEBHOOK_VERIFY_TOKEN_SECRET`

The `create_sub` task receives:

- the same shared runtime values as the worker where relevant
- `WEBHOOK_VERIFY_TOKEN_SECRET`
- `WEBHOOK_CALLBACK_URL`

Notes on consistency:

- `WEBHOOK_CALLBACK_URL` is no longer a Terraform input. It is derived from the API Gateway endpoint and injected into `create_sub`.
- `WEBHOOK_VERIFY_TOKEN` is not injected by default. It remains an optional runtime override and debug path; the standard production path is Secrets Manager via `WEBHOOK_VERIFY_TOKEN_SECRET`.

### Scheduled runs

`enable_schedule = true` creates an EventBridge Scheduler rule that runs the worker task with the same cluster and networking model as the normal ECS worker.

### Athena mode

`pipeline_query_engine = "athena"` creates:

- a Glue database
- `strava_raw_ext` at `s3://<bucket>/staging/strava/`
- `strava_main` at `s3://<bucket>/main/`

It also injects the Athena environment variables the worker expects so `app/staging/query_trigger.py` can execute `sql/pipeline_query.sql`.

## Secret Handling

Terraform creates the Secrets Manager objects but does not fully populate live values by default.

Default secret names are:

```text
<secret_prefix>-client-id
<secret_prefix>-client-secret
<secret_prefix>-auth-state
<secret_prefix>-webhook-verify-token
```

If you set:

```hcl
bootstrap_secrets = true
secret_values = {
  client_id     = "123"
  client_secret = "abc"
  auth_state    = "{\"refresh_token\":\"...\"}"
}
```

Terraform will create initial versions for:

- `client-id`
- `client-secret`
- `auth-state`

Important:

- the webhook verify token secret is not bootstrapped by `secret_values`
- the worker may update the `auth-state` secret during refresh token rotation
- do not put long-lived production secrets in version-controlled tfvars files

## Post-Apply Steps

### 1. Push the container image

Build the image from the repository root and push it to the ECR repository returned by `terraform output ecr_repository_url`.

### 2. Populate secrets

Set values for:

- `<secret_prefix>-client-id`
- `<secret_prefix>-client-secret`
- `<secret_prefix>-auth-state`
- `<secret_prefix>-webhook-verify-token`

### 3. Register the callback URL

Use the `webhook_callback_url` output returned by Terraform. The Strava callback must end with:

```text
/webhook
```

### 4. Run the subscription bootstrap task

Launch the `create_sub` task definition manually after the callback URL and verify token are ready.

Example AWS CLI shape:

```bash
aws ecs run-task \
  --cluster <ecs_cluster_name> \
  --launch-type FARGATE \
  --task-definition <create_subscription_task_definition_arn> \
  --network-configuration 'awsvpcConfiguration={subnets=["subnet-aaaa","subnet-bbbb"],securityGroups=["sg-aaaa"],assignPublicIp="ENABLED"}'
```

Use the same public subnets as `public_subnet_ids` and a security group with outbound internet access. `worker_security_group_id` is a suitable default for this task.

## What Terraform Does Not Do

This configuration intentionally does not:

- build or push Docker images
- create the VPC or subnets
- create Route 53 records or custom domains
- populate the webhook verify token automatically
- execute the `create_sub` task for you
- guarantee teardown of the S3 bucket during `terraform destroy`

The S3 bucket has `prevent_destroy = true`, so destructive cleanup must be handled deliberately.

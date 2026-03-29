# Terraform Deployment for Strava Pipeline

This directory is the canonical, preferred, and best-supported way to provision the Strava Pipeline on AWS.

The Terraform configuration matches the current application architecture:

- ECS Fargate runs all application modes
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

It does not create the VPC, subnet layout, Route 53 records, or ACM certificates for you.

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
- one webhook task definition and ECS service that runs `python -m app.main webhook`
- one `create_sub` task definition that runs `python -m app.main create_sub`
- one public ALB, target group, listeners, and security groups for the webhook service when enabled
- CloudWatch log groups for worker and webhook containers
- IAM roles and policies for ECS execution, worker runtime, and the optional scheduler
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

bucket_name       = "my-unique-strava-pipeline-bucket"
secret_prefix     = "strava"

enable_webhook_service = true
enable_schedule        = false

pipeline_query_engine = "none"
container_image       = ""

webhook_callback_url  = ""
webhook_certificate_arn = ""
```

Notes:

- `container_image = ""` means Terraform will point ECS at `<ecr_repository_url>:latest`.
- `webhook_callback_url` is optional at provisioning time but required before running `create_sub`.
- `webhook_certificate_arn` is optional. If you supply it, Terraform creates an HTTPS listener and HTTP-to-HTTPS redirect on the ALB.

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
- `webhook_service_name`
- `webhook_task_definition_arn`
- `webhook_alb_dns_name`
- `create_subscription_task_definition_arn`
- `scheduler_role_arn`

## Required Inputs

These values are required for a meaningful deployment:

| Variable | Purpose |
|----------|---------|
| `aws_region` | AWS provider region |
| `vpc_id` | Existing VPC for ECS and ALB resources |
| `public_subnet_ids` | Existing public subnets used by ALB, ECS service, and ECS tasks |
| `bucket_name` | S3 bucket name for state, raw, and staging data |

## Important Optional Inputs

Use these to shape the deployment:

| Variable | Default | Purpose |
|----------|---------|---------|
| `project_name` | `strava-pipeline` | Base name for AWS resources |
| `secret_prefix` | `strava` | Prefix for Secrets Manager names |
| `container_image` | `""` | Override the image used by ECS |
| `task_cpu` | `256` | CPU for ECS task definitions |
| `task_memory` | `512` | Memory for ECS task definitions |
| `enable_webhook_service` | `true` | Create the public webhook service and ALB |
| `webhook_desired_count` | `1` | Desired ECS service count for webhook containers |
| `webhook_cooldown_seconds` | `180` | Cooldown used by the webhook before triggering the worker again |
| `enable_schedule` | `false` | Create an EventBridge Scheduler job for the worker |
| `schedule_expression` | `rate(1 hour)` | Scheduler expression in UTC |
| `assign_public_ip` | `ENABLED` | Public IP behavior for ECS tasks |
| `pipeline_query_engine` | `none` | `none` or `athena` |
| `athena_database` | `""` | Required when Athena is enabled |
| `athena_output_s3` | `""` | Required when Athena is enabled |
| `athena_workgroup` | `""` | Optional Athena workgroup |
| `athena_timeout_seconds` | `300` | Athena polling timeout for the worker |
| `pipeline_sql_path` | `""` | Optional override for SQL file path inside the container |
| `app_env` | `{}` | Extra environment variables passed into the application containers |
| `tags` | `{}` | Extra AWS tags |

## Feature Flags and Modes

### Webhook service

`enable_webhook_service = true` creates:

- an internet-facing ALB
- webhook security groups
- an ECS service running the `webhook` mode
- a task definition with ECS trigger variables injected

The webhook container:

- serves `GET /webhook` for Strava verification
- serves `POST /webhook` for Strava events
- runs `ecs:RunTask` against the worker task definition

### Scheduled runs

`enable_schedule = true` creates an EventBridge Scheduler rule that runs the worker task with the same cluster and networking model as the normal ECS worker.

### Athena mode

`pipeline_query_engine = "athena"` creates:

- a Glue database
- `strava_raw_ext` at `s3://<bucket>/staging/strava/`
- `strava_main` at `s3://<bucket>/main/`

It also injects the Athena environment variables the worker expects so `app/staging/query_trigger.py` can execute `sql/pipeline_query.sql`.

## Secret Handling

Terraform creates the Secrets Manager objects but does not fully populate live values for you by default.

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

Terraform provisions infrastructure, but a working pipeline still needs a few operational steps.

### 1. Push the container image

Build the image from the repository root and push it to the ECR repository returned by `terraform output ecr_repository_url`.

If you rely on the default image path, push the image with the `latest` tag.

### 2. Populate secrets

Set values for:

- `<secret_prefix>-client-id`
- `<secret_prefix>-client-secret`
- `<secret_prefix>-auth-state`
- `<secret_prefix>-webhook-verify-token`

### 3. Finalize the webhook URL

Use the ALB endpoint returned by `webhook_alb_dns_name`, or front it with your own DNS and ACM certificate. The Strava callback must end with:

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

Use the same public subnets as `public_subnet_ids` and a security group with outbound internet access. The `worker_security_group_id` output is a suitable default for this task.

## Runtime Contract Created by Terraform

Terraform injects the application settings the current code expects:

- `BUCKET_NAME`
- `AWS_REGION`
- `SECRET_PREFIX`
- `PIPELINE_QUERY_ENGINE`
- optional Athena variables
- webhook ECS trigger variables:
  - `ECS_CLUSTER`
  - `ECS_TASK_DEFINITION`
  - `ECS_SUBNETS`
  - `ECS_SECURITY_GROUPS`
  - `ECS_ASSIGN_PUBLIC_IP`
  - `ECS_LAUNCH_TYPE`
  - `WEBHOOK_COOLDOWN_SECONDS`
  - `WEBHOOK_VERIFY_TOKEN_SECRET`
  - `PORT`
- `WEBHOOK_CALLBACK_URL` when provided

This is why Terraform is the best-supported implementation path for this repository: the infrastructure code and the Python runtime contract are already aligned.

## What Terraform Does Not Do

This configuration intentionally does not:

- build or push Docker images
- create the VPC or subnets
- create Route 53 records
- request or validate ACM certificates
- populate the webhook verify token automatically
- execute the `create_sub` task for you
- guarantee teardown of the S3 bucket during `terraform destroy`

The S3 bucket has `prevent_destroy = true`, so destructive cleanup must be handled deliberately.

## Notes for Operators

- The worker stores its state in `s3://<bucket>/state/strava_state.json`.
- Raw files are written under `s3://<bucket>/raw/strava/YYYY/MM/DD/`.
- Staging files are written under `s3://<bucket>/staging/strava/YYYY/MM/DD/`.
- CloudWatch log groups are `/ecs/<project>-worker` and `/ecs/<project>-webhook`.
- The worker, webhook, and `create_sub` task definitions share the same runtime IAM role, which is also allowed to read secrets and trigger the worker task.

## Common Workflow

For most deployments, the end-to-end sequence is:

1. Fill `terraform.tfvars`.
2. Run `terraform init`, `terraform plan`, and `terraform apply`.
3. Push the image to ECR.
4. Store the secret values in Secrets Manager.
5. Confirm the public webhook endpoint is reachable.
6. Run the `create_sub` task once.
7. Optionally enable the scheduler and Athena mode.

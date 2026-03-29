# Setup and Configuration Guide

## Overview

This repository targets AWS. The current runtime architecture is built around:

- ECS Fargate for all application modes
- S3 for raw, staging, and state storage
- AWS Secrets Manager for Strava credentials and webhook verification
- Application Load Balancer for public webhook ingress
- EventBridge Scheduler for optional cron-style worker runs
- ECR for container images
- CloudWatch Logs for runtime logs
- Athena and Glue as an optional SQL/query layer

Terraform in [`infra/terraform`](infra/terraform/README.md) is the canonical, preferred, and best-supported way to provision this stack. Manual AWS setup is possible, but the repository documentation assumes Terraform is the default implementation path.

## Runtime Modes

The container supports three execution modes:

| Mode | Entry Command | Deployment Shape | Purpose |
|------|---------------|------------------|---------|
| `worker` | `python -m app.main worker` | ECS Fargate task | Pull activities from Strava, write raw/staging data, update state, optionally run Athena SQL |
| `webhook` | `python -m app.main webhook` | ECS Fargate service behind ALB | Handle Strava webhook verification and event delivery, then trigger the worker task with `ecs:RunTask` |
| `create_sub` | `python -m app.main create_sub` | ECS Fargate task, launched manually | Create or recreate the Strava push subscription |

Entrypoint routing is implemented in `app/main.py`.

## Recommended Deployment Flow

### 1. Provision infrastructure with Terraform

Use the configuration in `infra/terraform` as the primary deployment path:

```bash
cd infra/terraform
terraform init
terraform plan
terraform apply
```

Terraform creates the AWS resources the application expects, including:

- S3 bucket
- Secrets Manager secrets
- ECR repository
- ECS cluster
- worker task definition
- webhook task definition and ECS service
- `create_sub` task definition
- ALB and target group for the webhook
- CloudWatch log groups
- optional EventBridge Scheduler schedule
- optional Glue catalog database and Athena tables

### 2. Build and push the container image

Build the image from the repository root:

```bash
docker build -t strava-pipeline:latest .
```

Authenticate Docker to ECR, tag the image with the repository URL returned by Terraform, and push it. If you do not set `container_image`, Terraform expects the image to exist at:

```text
<terraform output ecr_repository_url>:latest
```

### 3. Populate secrets

Terraform creates the secret objects, but it does not fully configure runtime values for you.

Required secrets are based on `SECRET_PREFIX`:

| Secret Name Pattern | Used By | Purpose |
|---------------------|---------|---------|
| `*-client-id` | `worker`, `create_sub` | Strava OAuth client id |
| `*-client-secret` | `worker`, `create_sub` | Strava OAuth client secret |
| `*-auth-state` | `worker` | Refresh token payload, usually JSON with `refresh_token` |
| `*-webhook-verify-token` | `webhook`, `create_sub` | Token used during Strava webhook verification |

Notes:

- `SECRET_PREFIX` defaults to `strava`.
- `bootstrap_secrets = true` can prefill `client_id`, `client_secret`, and `auth_state`.
- The webhook verify token secret is still expected to be set manually after apply.
- The worker updates the `*-auth-state` secret when Strava rotates the refresh token.

### 4. Point Strava at the webhook endpoint

If `enable_webhook_service = true`, Terraform exposes the webhook service through an ALB. The public callback URL you register with Strava must point to the `/webhook` path on that endpoint.

Typical forms are:

```text
<public-webhook-url>/webhook
```

If you configure `webhook_certificate_arn` and attach DNS, use your final HTTPS URL for Strava registration.

### 5. Run `create_sub` once

After the webhook endpoint and verify token are ready, run the `create_sub` task manually. This step is not automated by Terraform because it is an operational action against the live Strava API.

Use the `create_subscription_task_definition_arn` output together with the same public subnets and outbound security group pattern used by the worker task.

## Configuration Contract

### Core environment variables

These values are injected into containers by Terraform or supplied manually in local development:

| Variable | Used By | Required | Notes |
|----------|---------|----------|-------|
| `BUCKET_NAME` | `worker` | Yes | S3 bucket for state and pipeline files |
| `AWS_REGION` | All modes | Yes | AWS SDK region |
| `SECRET_PREFIX` | All modes | Yes | Defaults to `strava` when omitted |
| `PIPELINE_QUERY_ENGINE` | `worker` | No | `none` or `athena` |

### Webhook runtime variables

| Variable | Used By | Required | Notes |
|----------|---------|----------|-------|
| `ECS_CLUSTER` | `webhook` | Yes | Cluster name for `ecs:RunTask` |
| `ECS_TASK_DEFINITION` | `webhook` | Yes | Worker task definition ARN |
| `ECS_SUBNETS` | `webhook` | Yes | Comma-separated subnet ids |
| `ECS_SECURITY_GROUPS` | `webhook` | Yes | Comma-separated security group ids |
| `ECS_ASSIGN_PUBLIC_IP` | `webhook` | No | `ENABLED` or `DISABLED` |
| `ECS_LAUNCH_TYPE` | `webhook` | No | Defaults to `FARGATE` |
| `WEBHOOK_COOLDOWN_SECONDS` | `webhook` | No | Defaults to `180` |
| `WEBHOOK_VERIFY_TOKEN_SECRET` | `webhook`, `create_sub` | No | Overrides the default secret name |
| `PORT` | `webhook` | No | Defaults to `8080` |

### Subscription bootstrap variables

| Variable | Used By | Required | Notes |
|----------|---------|----------|-------|
| `WEBHOOK_CALLBACK_URL` | `create_sub` | Yes | Public Strava callback URL |
| `WEBHOOK_VERIFY_TOKEN` | `create_sub`, `webhook` | No | Optional direct override instead of Secrets Manager |

### Optional Athena variables

These are required only when `PIPELINE_QUERY_ENGINE=athena`:

| Variable | Used By | Required | Notes |
|----------|---------|----------|-------|
| `ATHENA_DATABASE` | `worker` | Yes | Glue/Athena database name |
| `ATHENA_OUTPUT_S3` | `worker` | Yes | Query results bucket/prefix |
| `ATHENA_WORKGROUP` | `worker` | No | Optional workgroup |
| `ATHENA_TIMEOUT_SECONDS` | `worker` | No | Defaults to `300` |
| `PIPELINE_SQL_PATH` | `worker` | No | Defaults to `sql/pipeline_query.sql` inside the container |

## Data Layout

### S3 object structure

The application writes the following keys under `BUCKET_NAME`:

```text
s3://BUCKET_NAME/
  state/
    strava_state.json
  raw/
    strava/YYYY/MM/DD/activities_<run_id>.jsonl
  staging/
    strava/YYYY/MM/DD/activities_<run_id>.jsonl
  main/
    ... optional Athena-managed output for downstream tables
```

Important details:

- `state/strava_state.json` is created by the application after the first successful run; no manual seed file is required.
- `raw/` stores append-only envelopes with the original activity JSON.
- `staging/` stores flattened activity rows used by Athena.
- `main/` is only relevant when your SQL pipeline materializes output there.

### Athena and Glue

If `pipeline_query_engine = "athena"`:

- Terraform creates a Glue database.
- Terraform creates `strava_raw_ext` over `s3://<bucket>/staging/strava/`.
- Terraform creates `strava_main` over `s3://<bucket>/main/`.
- The worker executes `sql/pipeline_query.sql` after raw/staging writes and state update.

If `pipeline_query_engine = "none"`, the worker skips the SQL step.

## IAM and Access Expectations

Terraform provisions the roles used by ECS tasks and the optional scheduler. In practical terms:

- the worker task can read and write the S3 bucket
- the worker task can read Strava secrets and update `*-auth-state`
- the webhook task can read the webhook verify token secret
- the webhook task can call `ecs:RunTask` for the worker task definition
- the scheduler role can run the worker task when scheduling is enabled

Manual deployments should preserve the same least-privilege shape.

## Local Development

### Prerequisites

```bash
pip install -r requirements.txt
```

You also need AWS credentials available to `boto3`, for example via:

- `aws configure`
- `aws sso login`
- `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`

### Example `.env`

```env
AWS_REGION=eu-north-1
BUCKET_NAME=my-strava-pipeline-bucket
SECRET_PREFIX=strava
PIPELINE_QUERY_ENGINE=none
WEBHOOK_CALLBACK_URL=http://localhost:8080/webhook
WEBHOOK_VERIFY_TOKEN=local-test-token
ECS_CLUSTER=strava-pipeline-cluster
ECS_TASK_DEFINITION=strava-pipeline-worker
ECS_SUBNETS=subnet-123,subnet-456
ECS_SECURITY_GROUPS=sg-123
ECS_ASSIGN_PUBLIC_IP=ENABLED
```

### Local entry commands

```bash
python -m app.main worker
python -m app.main webhook
python -m app.main create_sub
```

Notes:

- `worker` needs live AWS access for S3 and Secrets Manager.
- `webhook` can run locally for endpoint testing, but the ECS trigger still requires valid AWS configuration.
- `create_sub` calls the live Strava push subscription API.

## Troubleshooting

### Webhook receives verification traffic but returns `403`

- confirm the callback URL registered with Strava matches the public ALB endpoint
- confirm the stored `*-webhook-verify-token` value matches the token used during subscription creation
- confirm `WEBHOOK_VERIFY_TOKEN_SECRET` points at the expected secret name if you overrode defaults

### Webhook accepts requests but does not trigger the worker

- confirm `ECS_CLUSTER`, `ECS_TASK_DEFINITION`, `ECS_SUBNETS`, and `ECS_SECURITY_GROUPS` are present in the webhook task environment
- confirm the task role still has `ecs:RunTask` and `iam:PassRole`
- confirm outbound networking from the webhook task is available

### Worker fails before reading activities

- confirm `BUCKET_NAME`, `AWS_REGION`, and the Secrets Manager values exist
- confirm `*-auth-state` contains either a raw refresh token or JSON with `refresh_token`
- confirm the worker task role can read the required secrets

### Worker writes raw/staging files but fails during SQL

- confirm `PIPELINE_QUERY_ENGINE=athena`
- confirm `ATHENA_DATABASE` and `ATHENA_OUTPUT_S3` are set
- confirm the Glue database and tables exist in the same AWS account and region
- confirm the worker task role has Athena and Glue read permissions

### `create_sub` fails

- confirm the ALB endpoint is publicly reachable
- confirm `WEBHOOK_CALLBACK_URL` ends with `/webhook`
- confirm the verify token used for creation matches the value served by the webhook
- confirm the Strava client id and client secret secrets are populated

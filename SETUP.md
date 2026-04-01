# Setup and Configuration Guide

## Overview

This repository targets AWS and is designed around:

- API Gateway HTTP API and Lambda for public webhook ingress
- ECS Fargate for the worker and `create_sub`
- S3 for state, raw files, and staging files
- Secrets Manager for Strava credentials and webhook verification
- EventBridge Scheduler as an optional fallback trigger
- Athena and Glue as an optional SQL and analytics layer

Terraform in [`infra/terraform`](infra/terraform/README.md) is the canonical and best-supported deployment path.

## Runtime Surfaces

| Surface | Entry | Deployment Shape | Purpose |
|---------|-------|------------------|---------|
| Worker | `python -m app.main worker` | ECS Fargate task | Pull activities from Strava, write raw and staging data, update state, optionally run Athena SQL |
| Subscription bootstrap | `python -m app.main create_sub` | ECS Fargate task, launched manually | Verify the callback URL and register the Strava push subscription |
| Webhook ingress | `lambda_src/webhook_handler.lambda_handler` | Lambda behind API Gateway HTTP API | Serve `GET /webhook`, validate `POST /webhook`, trigger the worker via `ecs:RunTask` |

There is no longer a container webhook mode in `app.main`.

## Recommended Deployment Flow

### 1. Provision infrastructure with Terraform

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
- `create_sub` task definition
- Lambda webhook function and API Gateway HTTP API
- CloudWatch log groups
- optional EventBridge Scheduler schedule
- optional Glue database and Athena tables

### 2. Build and push the container image

Build from the repository root:

```bash
docker build -t strava-pipeline:latest .
```

Tag and push the image to the ECR repository returned by `terraform output ecr_repository_url`. If `container_image = ""`, Terraform expects the image at:

```text
<terraform output ecr_repository_url>:latest
```

### 3. Populate secrets

Terraform creates the secret objects, but you still need to populate live values.

Default secret names are based on `SECRET_PREFIX`:

| Secret Name Pattern | Used By | Purpose |
|---------------------|---------|---------|
| `*-client-id` | `worker`, `create_sub` | Strava OAuth client id |
| `*-client-secret` | `worker`, `create_sub` | Strava OAuth client secret |
| `*-auth-state` | `worker` | Refresh token payload, usually JSON with `refresh_token` |
| `*-webhook-verify-token` | Lambda webhook, `create_sub` | Verification token served during Strava webhook validation |

Notes:

- `SECRET_PREFIX` defaults to `strava`.
- `bootstrap_secrets = true` can prefill `client_id`, `client_secret`, and `auth_state`.
- The webhook verify token secret still needs to be populated manually.
- The worker may update the `*-auth-state` secret if Strava rotates the refresh token.

### 4. Register the callback URL in Strava

Use the Terraform output:

```bash
terraform output -raw webhook_callback_url
```

The value will look like:

```text
https://<api-id>.execute-api.<region>.amazonaws.com/webhook
```

### 5. Run `create_sub` once

After the webhook endpoint and verify token are ready, run the `create_sub` task manually. Terraform injects the callback URL automatically into that task.

Use `create_subscription_task_definition_arn` together with the same public subnets and outbound security group pattern used by the worker task.

## Runtime Variable Summary

### Worker

| Variable | Required | Notes |
|----------|----------|-------|
| `BUCKET_NAME` | Yes | S3 bucket for pipeline data and state |
| `AWS_REGION` | Yes | AWS SDK region |
| `SECRET_PREFIX` | No | Defaults to `strava` |
| `PIPELINE_QUERY_ENGINE` | No | `none` or `athena` |
| `ATHENA_DATABASE` | Athena only | Required when Athena is enabled |
| `ATHENA_OUTPUT_S3` | Athena only | Required when Athena is enabled |
| `ATHENA_WORKGROUP` | No | Optional |
| `ATHENA_TIMEOUT_SECONDS` | No | Defaults to `300` |
| `PIPELINE_SQL_PATH` | No | Defaults to `sql/pipeline_query.sql` in the image |

### `create_sub`

| Variable | Required | Notes |
|----------|----------|-------|
| `AWS_REGION` | Yes | Used by `boto3` |
| `SECRET_PREFIX` | No | Defaults to `strava` |
| `WEBHOOK_VERIFY_TOKEN_SECRET` | No | Overrides the default secret name |
| `WEBHOOK_VERIFY_TOKEN` | No | Optional override or debug path; Secrets Manager is the default source |
| `WEBHOOK_CALLBACK_URL` | Yes | Injected by Terraform in AWS; set manually only for local runs |

### Lambda webhook

| Variable | Required | Notes |
|----------|----------|-------|
| `ECS_CLUSTER` | Yes | ECS cluster used by `ecs:RunTask` |
| `ECS_TASK_DEFINITION` | Yes | Worker task definition ARN |
| `ECS_SUBNETS` | Yes | Comma-separated subnet ids |
| `ECS_SECURITY_GROUPS` | Yes | Comma-separated security group ids |
| `ECS_ASSIGN_PUBLIC_IP` | No | `ENABLED` or `DISABLED` |
| `ECS_LAUNCH_TYPE` | No | Defaults to `FARGATE` |
| `WEBHOOK_VERIFY_TOKEN_SECRET` | No | Default source for verification token |
| `WEBHOOK_VERIFY_TOKEN` | No | Optional override or debug path; Secrets Manager remains the default |

Spójność kontraktu wygląda teraz tak:

- `AWS_REGION` jest wspólne dla worker, `create_sub`, i Lambdy.
- `SECRET_PREFIX` jest wspólne dla ścieżek, które czytają sekrety po nazwie.
- `WEBHOOK_VERIFY_TOKEN` i `WEBHOOK_VERIFY_TOKEN_SECRET` nie dublują się funkcjonalnie: pierwszy to override, drugi to domyślna ścieżka produkcyjna.
- `WEBHOOK_CALLBACK_URL` nie jest już wejściem Terraforma, tylko wyliczanym outputem i env dla `create_sub`.

## Data Layout

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
    ... optional Athena-managed output
```

## Local Development

### Prerequisites

```bash
pip install -r requirements.txt
```

You also need AWS credentials available to `boto3`.

### Example `.env`

```env
AWS_REGION=eu-north-1
BUCKET_NAME=my-strava-pipeline-bucket
SECRET_PREFIX=strava
PIPELINE_QUERY_ENGINE=none
WEBHOOK_CALLBACK_URL=https://example.execute-api.eu-north-1.amazonaws.com/webhook
WEBHOOK_VERIFY_TOKEN=local-test-token
```

### Local entry commands

```bash
python -m app.main worker
python -m app.main create_sub
```

Notes:

- `worker` needs live AWS access for S3 and Secrets Manager.
- `create_sub` calls the live Strava push subscription API.
- The production webhook is Lambda-backed; local webhook simulation should be done by invoking `lambda_src/webhook_handler.lambda_handler` with a sample event, not by running a Flask service.

## Troubleshooting

### Webhook verification fails

- confirm the callback URL registered with Strava matches `terraform output -raw webhook_callback_url`
- confirm the stored `*-webhook-verify-token` value matches the token used during subscription creation
- confirm `WEBHOOK_VERIFY_TOKEN_SECRET` points at the expected secret name if you overrode defaults
- if you are testing locally, remember that `WEBHOOK_VERIFY_TOKEN` is only an override path

### Webhook accepts requests but does not trigger the worker

- confirm `ECS_CLUSTER`, `ECS_TASK_DEFINITION`, `ECS_SUBNETS`, and `ECS_SECURITY_GROUPS` are present in the Lambda environment
- confirm the Lambda IAM role still has `ecs:RunTask` and `iam:PassRole`
- confirm the worker task definition ARN in Lambda matches the active worker revision

### Worker fails before reading activities

- confirm `BUCKET_NAME`, `AWS_REGION`, and the required Secrets Manager values exist
- confirm `*-auth-state` contains a refresh token payload
- confirm the worker task role can read the required secrets

### Worker writes raw or staging files but fails during SQL

- confirm `PIPELINE_QUERY_ENGINE=athena`
- confirm `ATHENA_DATABASE` and `ATHENA_OUTPUT_S3` are set
- confirm the Glue database and tables exist in the same AWS account and region

### `create_sub` fails

- confirm the API Gateway endpoint is publicly reachable
- confirm `WEBHOOK_CALLBACK_URL` ends with `/webhook`
- confirm the verify token used for creation matches the value served by the Lambda webhook
- confirm the Strava client id and client secret secrets are populated

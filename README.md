# Strava Pipeline

Event-driven analytics pipeline on AWS for ingesting Strava activities, persisting raw and curated data in S3, materializing analytics tables in Athena, and exposing the result to Grafana.

## Architecture

`Strava -> API Gateway HTTP API -> Lambda webhook -> ECS RunTask(worker) -> S3 raw/staging -> Athena -> Grafana`

The public ingress is fully serverless. API Gateway and Lambda handle webhook verification and event delivery, and the Lambda handler triggers the ECS worker on demand. The worker remains responsible for fetching activities, filtering by checkpoint state, writing files to S3, and optionally running the Athena SQL step.

## Runtime Surfaces

| Surface | Entry | Responsibility |
|---------|-------|----------------|
| Webhook ingress | `lambda_src/webhook_handler.lambda_handler` | Strava verification, webhook event validation, `ecs:RunTask` trigger |
| Worker task | `python -m app.main worker` | Fetch activities, update state, write raw/staging data, run Athena SQL |
| Subscription bootstrap | `python -m app.main create_sub` | Preflight the callback URL and register or reuse the Strava push subscription |

## Stack

- Python 3.11, `requests`, `boto3`, `python-dotenv`
- AWS Lambda, API Gateway HTTP API, ECS Fargate, S3, Secrets Manager, Athena, Glue, ECR
- Terraform for infrastructure provisioning
- Grafana querying Athena as the reporting layer

## Analytics Output

![Anonymized Grafana dashboard](docs/images/grafana-dashboard-anonymized.png)

The dashboard is included as proof that the pipeline ends in an analytics-ready consumption layer, not just raw JSON landing. The recent activity table is redacted for public sharing; the goal here is to show the data product, not personal ride details.

## Key Engineering Decisions

- Webhook-first ingestion instead of constant polling as the primary trigger path.
- Decoupled trigger and worker: Lambda owns ingress, ECS owns the heavier ingestion work.
- Incremental processing with checkpoint state stored in S3.
- Layered storage model: `raw/`, `staging/`, and Athena-managed `main/`.
- Terraform-first deployment so the runtime contract and AWS resources stay aligned.

## Repository Docs

- [SETUP.md](SETUP.md) covers deployment, secrets, runtime variables, and local development.
- [infra/terraform/README.md](infra/terraform/README.md) documents the AWS stack, Terraform inputs, outputs, and runtime contract.
- [scheme.txt](scheme.txt) provides a concise repository and architecture map.

## Current Scope

This repository demonstrates a working cloud analytics pipeline rather than a fully packaged product. Natural next steps would be:

- richer retry and dead-letter handling
- stronger monitoring and alerting
- more operational dashboards around freshness and failed runs

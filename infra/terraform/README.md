# Terraform (ECS Fargate)

This folder provisions AWS resources for the Strava worker job.
It uses existing VPC and public subnets and does not create any networking.

## What gets created

- S3 bucket for raw, staging, and state files
- Secrets Manager secrets for Strava credentials
- ECR repository for the container image
- ECS cluster and task definition for the worker
- CloudWatch log group for task logs
- Optional EventBridge Scheduler for cron-like runs

## Quick start

1. Create a `terraform.tfvars` file in this folder with your values.

Example:

```hcl
aws_region        = "eu-north-1"
project_name      = "strava-pipeline"
vpc_id            = "vpc-xxxxxxxx"
public_subnet_ids = ["subnet-xxxxxxxx"]

bucket_name       = "my-unique-bucket-name"
container_image   = "" # defaults to the ECR repo with :latest

enable_schedule   = false
pipeline_query_engine = "none"
secret_prefix     = "strava"
```

2. Initialize and apply:

```bash
terraform init
terraform plan
terraform apply
```

## Terraform basics (for first-time use)

Terraform reads `.tf` files, compares them to what exists in AWS, and then creates
or updates resources to match the code.

Key commands:

- `terraform init` downloads providers and prepares the working directory.
- `terraform plan` shows what will be created or changed.
- `terraform apply` performs the changes.
- `terraform output` shows values exported from the configuration.
- `terraform destroy` removes everything created by this configuration.

Terraform keeps state in a local file (`terraform.tfstate`) inside this folder.
That file should not be committed to git.

## First apply checklist

1. Ensure Terraform is installed:
```bash
terraform -version
```

2. Ensure AWS credentials are available to Terraform. Use one of:
- AWS CLI profiles (`aws configure` or `aws sso login`)
- Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, optional `AWS_SESSION_TOKEN`)

3. Run the standard sequence:
```bash
terraform init
terraform plan
terraform apply
```

4. After apply, see outputs:
```bash
terraform output
```

5. Next steps:
- Push the container image to the ECR repo shown in outputs.
- Set secrets in Secrets Manager.

## Secrets

By default, Terraform creates empty Secrets Manager secrets and does not set values.
This avoids putting secrets in Terraform state.

If you want Terraform to set the secret values, enable bootstrapping:

```hcl
bootstrap_secrets = true
secret_values = {
  client_id     = "123"
  client_secret = "abc"
  auth_state    = "{\"refresh_token\":\"...\"}"
}
```

## Running the worker

- Build and push the Docker image to ECR.
- Update `container_image` if you use a tag other than `latest`.
- Run the task manually or enable the scheduler.

## Webhook service (Strava -> ECS trigger)

This config can also run a public webhook service that triggers the worker task.
By default it creates:
- An internet-facing ALB
- An ECS service running `python -m app.main webhook`

Set these variables as needed:

```hcl
enable_webhook_service = true
webhook_callback_url   = "" # optional, for create_subscription task
webhook_certificate_arn = "" # optional, HTTPS listener if provided
```

After `apply`, check `webhook_alb_dns_name` output and point your Strava callback URL to:

```
http://<alb-dns-name>/webhook
```

If you enable HTTPS with an ACM cert, use:

```
https://<your-domain>/webhook
```

You must also set the Secrets Manager value for `${secret_prefix}-webhook-verify-token`.

## Athena (optional)

If you want Athena query execution, set:

```hcl
pipeline_query_engine = "athena"
athena_database       = "your_database"
athena_output_s3      = "s3://your-bucket/athena-output/"
athena_workgroup      = "" # optional
pipeline_sql_path     = "" # optional
```

Terraform will also create a Glue catalog database and two external tables:
- `strava_raw_ext` mapped to `s3://<bucket>/staging/strava/` (JSONL)
- `strava_main` mapped to `s3://<bucket>/main/` (Parquet)

## Notes

- This setup assumes public subnets with Internet Gateway access.
- The task is configured with `assign_public_ip = "ENABLED"` by default.

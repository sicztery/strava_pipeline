# Setup and Configuration Guide

## Overview

The Strava Pipeline has three execution modes:

| Mode | Type | Purpose | Trigger |
|------|------|---------|---------|
| `webhook` | Service | Receives Strava webhook events and triggers worker runs | Cloud Run service |
| `worker` | Job | Fetches Strava activities, writes data, executes SQL pipeline | Cloud Run job |
| `create_sub` | One-time Job | Creates/recreates Strava webhook subscription | Manual run |

Entrypoint routing:

```bash
python -m app.main webhook
python -m app.main worker
python -m app.main create_sub
```

## Identity Model (Least Privilege)

Use separate service accounts. Do not run all components with one broad account.

Suggested principals:

| Principal | Used by | Responsibility |
|----------|---------|----------------|
| `sa-webhook` | Cloud Run service (`webhook`) | Invoke worker job on incoming event |
| `sa-worker` | Cloud Run job (`worker`) | Read/write state and data, call Strava, run BigQuery |
| `sa-create-sub` | Cloud Run job (`create_sub`) | Read Strava app secrets and create webhook subscription |
| `sa-scheduler` | Cloud Scheduler | Invoke Cloud Run worker job |
| `sa-cloud-build` | Cloud Build runtime | Build image and push to Artifact Registry |
| `ci-cd-operator` (user or SA) | CI/CD administration | Edit Cloud Build pipeline config/triggers |

## Minimum IAM Permissions

### 1) `sa-worker` (runtime worker)

Scope IAM as narrowly as possible (dataset, bucket, specific secrets).

Required:

- `roles/storage.objectAdmin` on the pipeline bucket (or a custom role with:
  `storage.buckets.get`, `storage.objects.get`, `storage.objects.create`)
- `roles/bigquery.jobUser` on project (required to create query jobs)
- `roles/bigquery.dataEditor` on dataset `BQ_DATASET` (required for `INSERT INTO`)
- `roles/secretmanager.secretAccessor` on:
  - `strava-client-id`
  - `strava-client-secret`
  - `strava-refresh-token`

If refresh token rotation writes a new secret version:

- `roles/secretmanager.secretVersionAdder` on `strava-refresh-token`

If your process also needs to manage secret version lifecycle (enable/disable/destroy):

- `roles/secretmanager.secretVersionManager` on `strava-refresh-token`

### 2) `sa-webhook` (runtime webhook)

Required to trigger worker Cloud Run job:

- `roles/run.jobsExecutor` on the target worker job  
  (If your organization does not use this role, use `roles/run.invoker` as fallback.)

### 3) `sa-create-sub` (subscription bootstrap job)

Required:

- `roles/secretmanager.secretAccessor` on:
  - `strava-client-id`
  - `strava-client-secret`

No BigQuery or GCS permissions are required for this mode.

### 4) `sa-scheduler` (Cloud Scheduler caller)

Required:

- `roles/run.invoker` (or `roles/run.jobsExecutor`) on worker job

This account is used in Scheduler OIDC auth when calling `jobs:run`.

### 5) `sa-cloud-build` (build runtime)

Required:

- `roles/artifactregistry.writer` on target Artifact Registry repository

### 6) `ci-cd-operator` (build pipeline editor)

Required:

- `roles/cloudbuild.builds.editor`

Use this only for identities that must edit Cloud Build definitions/triggers.

## Environment Variables

### Required

| Variable | Type | Example | Used By |
|----------|------|---------|---------|
| `STRAVA_GCP_PROJECT` | String | `my-gcp-project-id` | All modes |
| `BUCKET_NAME` | String | `strava-pipeline-bucket` | Worker |
| `BQ_DATASET` | String | `strava_raw` | Worker |
| `WEBHOOK_VERIFY_TOKEN` | String | `abc123xyz` | Webhook, create_sub |
| `WEBHOOK_CALLBACK_URL` | String | `https://my-webhook.run.app/webhook` | create_sub |
| `STRAVA_WORKER_JOB` | String | `strava-worker` | Webhook |

### Optional

| Variable | Default | Used By |
|----------|---------|---------|
| `STRAVA_GCP_REGION` | `europe-west1` | Webhook |
| `BQ_LOCATION` | `europe-west1` | Worker |
| `WEBHOOK_COOLDOWN_SECONDS` | `180` | Webhook |
| `PORT` | `8080` | Webhook |

## Secret Manager vs GCS State

Clarification:

- `strava-refresh-token` is stored in **Secret Manager**.
- `strava-auth-state` is **not a secret**. It is persisted as state in **GCS**.

### Secret Manager objects

| Secret Name | Used By | Purpose |
|-------------|---------|---------|
| `strava-client-id` | Worker, create_sub | Strava OAuth client id |
| `strava-client-secret` | Worker, create_sub | Strava OAuth client secret |
| `strava-refresh-token` | Worker | Strava OAuth refresh token |

## Cloud Storage Setup

The worker uses `BUCKET_NAME` for raw payloads, staging payloads, and pipeline state.

Structure:

```text
gs://BUCKET_NAME/
  state/
    strava_state.json
  raw/
    strava/YYYY/MM/DD/activities_<run_id>.jsonl
  staging/
    strava/YYYY/MM/DD/activities_<run_id>.jsonl
```

Initialization:

```bash
gsutil mb -l europe-west1 gs://strava-pipeline-bucket
echo '{"last_seen_timestamp": 0, "last_seen_activity_id": 0}' | \
  gsutil cp - gs://strava-pipeline-bucket/state/strava_state.json
```

## BigQuery Setup

The worker executes SQL from `sql/pipeline_query.sql`.

Current SQL writes into:

- `${PROJECT_ID}.${BQ_DATASET}.strava_main`

Current SQL reads from:

- `${PROJECT_ID}.${BQ_DATASET}.strava_raw_ext`

You must create dataset/tables/views/external tables required by that SQL before first run, unless your deployment automation creates them.

## Build and Deploy

### Build image

```bash
docker build -t strava-pipeline:latest .
```

### Deploy webhook service

```bash
gcloud run deploy strava-webhook \
  --image REGION-docker.pkg.dev/PROJECT/REPO/strava-pipeline:latest \
  --region europe-west1 \
  --service-account sa-webhook@PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars "STRAVA_GCP_PROJECT=PROJECT_ID,WEBHOOK_VERIFY_TOKEN=TOKEN,STRAVA_WORKER_JOB=strava-worker,STRAVA_GCP_REGION=europe-west1" \
  --args "webhook"
```

### Deploy worker job

```bash
gcloud run jobs create strava-worker \
  --image REGION-docker.pkg.dev/PROJECT/REPO/strava-pipeline:latest \
  --region europe-west1 \
  --service-account sa-worker@PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars "STRAVA_GCP_PROJECT=PROJECT_ID,BUCKET_NAME=strava-pipeline-bucket,BQ_DATASET=strava_raw,BQ_LOCATION=europe-west1" \
  --args "worker"
```

### Deploy create_sub job

```bash
gcloud run jobs create strava-create-sub \
  --image REGION-docker.pkg.dev/PROJECT/REPO/strava-pipeline:latest \
  --region europe-west1 \
  --service-account sa-create-sub@PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars "STRAVA_GCP_PROJECT=PROJECT_ID,WEBHOOK_VERIFY_TOKEN=TOKEN,WEBHOOK_CALLBACK_URL=https://my-webhook.run.app/webhook" \
  --args "create_sub"
```

### Run one-time webhook subscription setup

```bash
gcloud run jobs execute strava-create-sub --region europe-west1
```

## Cloud Scheduler (Optional)

Example (hourly):

```bash
gcloud scheduler jobs create http strava-worker-schedule \
  --location=europe-west1 \
  --schedule="0 * * * *" \
  --http-method=POST \
  --uri="https://run.googleapis.com/v2/projects/PROJECT_ID/locations/europe-west1/jobs/strava-worker:run" \
  --oidc-service-account-email="sa-scheduler@PROJECT_ID.iam.gserviceaccount.com"
```

## Cloud Build and Artifact Registry (CI/CD)

Your CI pipeline needs:

- Cloud Build runtime SA with `roles/artifactregistry.writer`
- CI/CD operator identity with `roles/cloudbuild.builds.editor`

`cloudbuild.yaml` builds and publishes `${_IMAGE}`. Ensure `_IMAGE` points to your Artifact Registry path.

## Local Development

### Prerequisites

```bash
pip install -r requirements.txt
gcloud auth application-default login
```

### `.env` example

```env
STRAVA_GCP_PROJECT=my-project
BUCKET_NAME=my-bucket
BQ_DATASET=strava_raw
WEBHOOK_VERIFY_TOKEN=local-test-token
WEBHOOK_CALLBACK_URL=http://localhost:8080/webhook
STRAVA_WORKER_JOB=strava-worker
BQ_LOCATION=europe-west1
STRAVA_GCP_REGION=europe-west1
```

### Run modes locally

```bash
python -m app.main webhook
python -m app.main worker
python -m app.main create_sub
```

## Troubleshooting

### Webhook cannot trigger worker job

- Verify `sa-webhook` has `run.jobsExecutor` (or `run.invoker`) on worker job
- Verify `STRAVA_WORKER_JOB` and `STRAVA_GCP_REGION` are correct

### Worker fails on BigQuery `INSERT INTO`

- Verify `sa-worker` has `roles/bigquery.jobUser` on project
- Verify `sa-worker` has `roles/bigquery.dataEditor` on dataset
- Verify `BQ_LOCATION` matches dataset region

### Worker fails to read/write GCS

- Verify bucket name and region
- Verify `sa-worker` bucket permissions (`storage.objects.get/create` at minimum)

### Secret read/write errors

- Verify secret names exist
- Verify `secretAccessor` on required secrets
- If rotating refresh token versions, verify `secretVersionAdder`

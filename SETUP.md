# Setup & Configuration Guide

## Overview

The Strava Pipeline consists of three main execution modes, each with a distinct role:

| Mode | Type | Purpose | Trigger |
|------|------|---------|---------|
| `webhook` | Service | Listens for Strava events and triggers the worker job | Cloud Run service (always running) |
| `worker` | Job | Fetches and processes activity data from Strava API | Cloud Run job (scheduled or event-driven) |
| `create_sub` | One-time Job | Sets up Strava webhook subscription (run once during setup) | Manual execution |

## Entrypoint: main.py

The **`main.py`** file acts as a **router** that directs execution to the appropriate mode based on a container argument:

```bash
# Start webhook service
python -m app.main webhook

# Run worker job
python -m app.main worker

# Create subscription (one-time setup)
python -m app.main create_sub
```

The Docker container is invoked with these arguments by Cloud Run, determining which component runs.

---

## Execution Modes

### 1. Webhook Service (`webhook` mode)

**Role:** Real-time event listener and job orchestrator

The webhook service:
- Runs as a **persistent Cloud Run service** (always listening)
- Receives HTTP POST requests from Strava when an activity is created/updated
- Validates incoming events (token verification, rate limiting)
- **Triggers the worker Cloud Run job** when a valid activity event arrives
- Implements cooldown logic to prevent excessive job triggers

**Key Features:**
- Rate limiting (30 req/min per IP, 200/day global)
- Token-based security (`WEBHOOK_VERIFY_TOKEN`)
- Cooldown mechanism (`WEBHOOK_COOLDOWN_SECONDS`) to avoid redundant worker invocations
- Uses `google-cloud-run` client to trigger worker jobs

**Configuration:**
- Exposed on Cloud Run as an HTTPS endpoint
- PORT defaults to `8080`

---

### 2. Worker Job (`worker` mode) / `strava_client`

**Role:** Core activity ingestion and transformation logic

The worker:
- Runs as a **Cloud Run job** (stateless, ephemeral execution)
- Can be triggered by:
  - **Webhook** (event-driven, real-time)
  - **Cloud Scheduler** (cron-based, periodic safety net)
- Executes the complete data pipeline:
  1. Authenticates with Strava API
  2. Loads last-seen state from Cloud Storage
  3. Fetches new activities from Strava API
  4. Filters and deduplicates activities
  5. Writes raw data to Cloud Storage
  6. Transforms and stages data in BigQuery
  7. Executes analytics pipeline queries
  8. Saves updated state back to Cloud Storage

**Pipeline Flow:**
```
Load State → Fetch Strava API → Filter Duplicates → Write Raw (GCS) 
  → Transform → Write Staging (BigQuery) → Run Queries
```

**State Management:**
- Tracks `last_seen_timestamp` and `last_seen_activity_id` to avoid reprocessing
- State persisted in Cloud Storage

---

### 3. Create Subscription Job (`create_sub` mode)

**Role:** One-time setup for Strava webhook integration

The subscription creator:
- Runs as a **one-time Cloud Run job** (executed manually during deployment)
- Calls Strava's push subscription API to register the webhook endpoint
- Validates the callback URL is accessible from Strava
- **Run this once after deploying the webhook service**

**When to use:**
```bash
# After webhook service is deployed and ready to receive traffic
python -m app.main create_sub
```

---

## Environment Variables

### Required Variables

| Variable | Type | Example | Used By |
|----------|------|---------|---------|
| `STRAVA_GCP_PROJECT` | String | `my-gcp-project-id` | All modes |
| `BUCKET_NAME` | String | `strava-pipeline-bucket` | Worker, state manager |
| `BQ_DATASET` | String | `strava_raw` | Worker (BigQuery) |
| `WEBHOOK_VERIFY_TOKEN` | String | `abc123xyz` | Webhook, create_sub |
| `WEBHOOK_CALLBACK_URL` | String | `https://webhook-service-url.run.app/webhook` | create_sub |

### Optional Variables

| Variable | Default | Used By |
|----------|---------|---------|
| `STRAVA_GCP_REGION` | `europe-west1` | Webhook |
| `BQ_LOCATION` | `europe-west1` | Worker (BigQuery queries) |
| `WEBHOOK_COOLDOWN_SECONDS` | `180` | Webhook |
| `STRAVA_WORKER_JOB` | *(required)* | Webhook (must match Cloud Run job name) |
| `PORT` | `8080` | Webhook service |

### Secrets in Google Secret Manager

The following credentials are fetched from **Google Secret Manager** (project: `STRAVA_GCP_PROJECT`):

| Secret Name | Used By | Purpose |
|------------|---------|---------|
| `strava-client-id` | Worker, create_sub | OAuth client ID for Strava API |
| `strava-client-secret` | Worker, create_sub | OAuth client secret for Strava API |
| `strava-refresh-token` | Worker | Refresh token for offline API access |

---

## Cloud Storage Bucket Setup

The pipeline uses a **Google Cloud Storage bucket** (`BUCKET_NAME`) to store:

### Structure:

```
gs://BUCKET_NAME/
├── state/
│   └── last_seen.json          # Current pipeline state (timestamp, activity_id)
├── raw/
│   └── {date}/{activity_id}.json  # Raw activity JSON from Strava API
└── staging/
    └── (optional) transformed data before BigQuery
```

### Bucket Permissions:

The service account running the pipeline requires:
- `storage.objects.get` – Load state
- `storage.objects.create` – Write raw data and state
- `storage.buckets.get` – Verify bucket existence

### Initialization:

Create the bucket and directory structure:

```bash
# Create bucket
gsutil mb -l europe-west1 gs://strava-pipeline-bucket

# Create initial state file (optional)
echo '{"last_seen_timestamp": 0, "last_seen_activity_id": 0}' | \
  gsutil cp - gs://strava-pipeline-bucket/state/last_seen.json
```

---

## BigQuery Setup

The pipeline writes activity data to **BigQuery** tables in dataset `BQ_DATASET`.

### Required Tables:

- **`raw_activities`** – Raw activity data from Strava API (one row per activity)
- **`staging_activities`** – Transformed, deduplicated activity data (staging layer)

### BigQuery Permissions:

The service account requires:
- `bigquery.datasets.get` – Dataset access
- `bigquery.tables.get` – Table metadata
- `bigquery.tables.create` – Create tables (if not pre-created)
- `bigquery.tables.update` – Update table schema
- `bigquery.tabledata.insertAll` – Insert rows

### Schema Example:

See [pipeline_schema.sql](./sql/pipeline_query.sql) for table definitions.

---

## Docker & Cloud Run Deployment

### Building the Docker Image

```bash
docker build -t strava-pipeline:latest .
```

The `Dockerfile` uses `main.py` as the entrypoint, respecting the mode argument.

### Deploying Webhook Service

```bash
gcloud run deploy strava-webhook \
  --image strava-pipeline:latest \
  --platform managed \
  --region europe-west1 \
  --timeout 30 \
  --set-env-vars "STRAVA_GCP_PROJECT=my-project,BUCKET_NAME=my-bucket,BQ_DATASET=strava_raw,WEBHOOK_VERIFY_TOKEN=secret,STRAVA_WORKER_JOB=strava-worker" \
  --args "webhook"
```

### Deploying Worker Job

```bash
gcloud run jobs create strava-worker \
  --image strava-pipeline:latest \
  --platform managed \
  --region europe-west1 \
  --task-timeout 600 \
  --set-env-vars "STRAVA_GCP_PROJECT=my-project,BUCKET_NAME=my-bucket,BQ_DATASET=strava_raw" \
  --args "worker"
```

### Triggering Worker with Cloud Scheduler (Optional)

```bash
gcloud scheduler jobs create cloud-run strava-worker-schedule \
  --location europe-west1 \
  --schedule "0 * * * *" \
  --http-method POST \
  --uri "https://region-project.cloudjobs.googleapis.com/v1/projects/project/locations/region/jobs/strava-worker:run" \
  --oidc-service-account-email "your-sa@project.iam.gserviceaccount.com"
```

---

## Local Development

### Prerequisites

```bash
pip install -r requirements.txt
```

### Environment Setup

Create a `.env` file in the project root:

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

For local development, ensure you have:
- **Google Cloud SDK** (`gcloud` CLI)
- **Authenticated credentials** (`gcloud auth application-default login`)
- Access to the GCP project resources (Cloud Storage, BigQuery, Secret Manager)

### Running Modes Locally

```bash
# Run webhook service
python -m app.main webhook

# Run worker job
python -m app.main worker

# Run subscription setup
python -m app.main create_sub
```

---

## Troubleshooting

### Webhook service not receiving events
- Verify `WEBHOOK_CALLBACK_URL` is publicly accessible
- Check that `WEBHOOK_VERIFY_TOKEN` matches Strava configuration
- Use `create_sub` to recreate the subscription with the correct URL

### Worker job fails with BigQuery errors
- Ensure `BQ_DATASET` exists and service account has write permissions
- Verify table schemas match expected column names
- Check `BQ_LOCATION` matches your dataset region

### State not persisting between runs
- Verify `BUCKET_NAME` exists and service account has write permissions
- Check Cloud Storage IAM roles include `roles/storage.objectAdmin` or equivalent

### Rate limiting on webhook
- Adjust `WEBHOOK_COOLDOWN_SECONDS` to prevent excessive worker triggers
- Monitor Cloud Run logs for rate limit hits


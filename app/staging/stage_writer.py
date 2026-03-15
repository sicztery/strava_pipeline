import json
import os
from datetime import datetime
from google.cloud import storage

# ======================
# CONFIG
# ======================

BUCKET_NAME = os.getenv("BUCKET_NAME")
if not BUCKET_NAME:
    raise RuntimeError("Missing env var: BUCKET_NAME")


def write_staging(activities: list[dict], run_id: str):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)

    today = datetime.utcnow().strftime("%Y/%m/%d")
    blob_path = f"staging/strava/{today}/activities_{run_id}.jsonl"

    blob = bucket.blob(blob_path)

    payload = "\n".join(json.dumps(a) for a in activities) + "\n"

    blob.upload_from_string(
        payload,
        content_type="application/json"
    )

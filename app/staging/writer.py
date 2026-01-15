import json
from datetime import datetime
from google.cloud import storage
import logging

logger = logging.getLogger("strava_pipeline")

BUCKET_NAME = "strava-raw-alpine-proton-482413"


def write_staging(activities: list[dict]):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)

    today = datetime.utcnow().strftime("%Y/%m/%d")
    blob_path = f"staging/strava/{today}/activities.jsonl"

    blob = bucket.blob(blob_path)

    payload = "\n".join(json.dumps(a) for a in activities) + "\n"

    blob.upload_from_string(
        payload,
        content_type="application/json"
    )

    logger.info(
        f"STAGING WRITE → {len(activities)} records to gs://{BUCKET_NAME}/{blob_path}"
    )

import os
import json
from google.cloud import storage

BUCKET_NAME = os.getenv("STRAVA_RAW_BUCKET")
if not BUCKET_NAME:
    raise RuntimeError("Missing env var: STRAVA_RAW_BUCKET")
STATE_BLOB = "state/strava_state.json"


def load_state():
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(STATE_BLOB)

    if not blob.exists():
        return None, None

    data = json.loads(blob.download_as_text())
    return data["last_seen_timestamp"], data["last_seen_activity_id"]


def save_state(last_seen_timestamp, last_seen_activity_id):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(STATE_BLOB)

    payload = {
        "last_seen_timestamp": last_seen_timestamp,
        "last_seen_activity_id": last_seen_activity_id,
    }

    blob.upload_from_string(
        json.dumps(payload),
        content_type="application/json"
    )


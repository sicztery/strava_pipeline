import os
import json
import boto3
from botocore.exceptions import ClientError

# ======================
# CONFIG
# ======================

BUCKET_NAME = os.getenv("BUCKET_NAME")
if not BUCKET_NAME:
    raise RuntimeError("Missing env var: BUCKET_NAME")
STATE_BLOB = "state/strava_state.json"


def _client():
    region = os.getenv("AWS_REGION")
    if region:
        return boto3.client("s3", region_name=region)
    return boto3.client("s3")


def load_state():
    client = _client()

    try:
        response = client.get_object(
            Bucket=BUCKET_NAME,
            Key=STATE_BLOB
        )
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("NoSuchKey", "404", "NotFound"):
            return None, None
        raise

    body = response["Body"].read().decode("utf-8")
    data = json.loads(body)
    return data["last_seen_timestamp"], data["last_seen_activity_id"]


def save_state(last_seen_timestamp, last_seen_activity_id):
    client = _client()

    payload = {
        "last_seen_timestamp": last_seen_timestamp,
        "last_seen_activity_id": last_seen_activity_id,
    }

    client.put_object(
        Bucket=BUCKET_NAME,
        Key=STATE_BLOB,
        Body=json.dumps(payload).encode("utf-8"),
        ContentType="application/json"
    )


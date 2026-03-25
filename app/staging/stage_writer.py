import json
import os
from datetime import datetime
import boto3

# ======================
# CONFIG
# ======================

BUCKET_NAME = os.getenv("BUCKET_NAME")
if not BUCKET_NAME:
    raise RuntimeError("Missing env var: BUCKET_NAME")


def write_staging(activities: list[dict], run_id: str):
    region = os.getenv("AWS_REGION")
    if region:
        client = boto3.client("s3", region_name=region)
    else:
        client = boto3.client("s3")

    today = datetime.utcnow().strftime("%Y/%m/%d")
    blob_path = f"staging/strava/{today}/activities_{run_id}.jsonl"

    payload = "\n".join(json.dumps(a) for a in activities) + "\n"

    client.put_object(
        Bucket=BUCKET_NAME,
        Key=blob_path,
        Body=payload.encode("utf-8"),
        ContentType="application/json"
    )

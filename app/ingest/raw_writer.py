import json
import os
from datetime import datetime, timezone
from typing import List, Dict

import boto3

# ======================
# CONFIG
# ======================

BUCKET_NAME = os.getenv("BUCKET_NAME")
if not BUCKET_NAME:
    raise RuntimeError("Missing env var: BUCKET_NAME")


# ======================
# MODULE API
# ======================

def write_raw(
    activities: List[Dict],
    run_id: str,
) -> None:
    """
    TRUE APPEND write of raw Strava data to GCS.

    - one file = one run
    - semantic append (never overwrite)
    - envelope preserved (as in local version)
    """

    if not activities:
        return

    region = os.getenv("AWS_REGION")
    if region:
        client = boto3.client("s3", region_name=region)
    else:
        client = boto3.client("s3")

    today = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    blob_path = f"raw/strava/{today}/activities_{run_id}.jsonl"

    lines = []
    ingested_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for activity in activities:
        row = {
            "activity_id": int(activity["id"]),
            "start_date": activity["start_date"],
            "ingested_at": ingested_at,
            "raw_json": activity,
        }
        lines.append(json.dumps(row, ensure_ascii=False))

    payload = "\n".join(lines) + "\n"

    client.put_object(
        Bucket=BUCKET_NAME,
        Key=blob_path,
        Body=payload.encode("utf-8"),
        ContentType="application/json"
    )





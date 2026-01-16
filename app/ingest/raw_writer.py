import json
from datetime import datetime, timezone
from typing import List, Dict

from google.cloud import storage

# ======================
# KONFIGURACJA
# ======================

BUCKET_NAME = "strava-raw-alpine-proton-482413"


# ======================
# API MODUŁU
# ======================

def write_raw(
    activities: List[Dict],
    run_id: str,
) -> None:
    """
    TRUE APPEND zapis RAW danych Stravy do GCS.

    - jeden plik = jeden run
    - append semantyczny (nigdy nie nadpisujemy)
    - envelope zachowany (jak w wersji lokalnej)
    """

    if not activities:
        return

    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)

    today = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    blob_path = f"raw/strava/{today}/activities_{run_id}.jsonl"

    blob = bucket.blob(blob_path)

    lines = []
    ingested_at = datetime.now(timezone.utc).isoformat()

    for activity in activities:
        row = {
            "activity_id": int(activity["id"]),
            "start_date": activity["start_date"],
            "ingested_at": ingested_at,
            "raw_json": activity,
        }
        lines.append(json.dumps(row, ensure_ascii=False))

    payload = "\n".join(lines) + "\n"

    blob.upload_from_string(
        payload,
        content_type="application/json"
    )



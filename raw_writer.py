import json
import os
from datetime import datetime, timezone
from typing import List, Dict

RAW_FILE = os.path.join(
    os.path.dirname(__file__),
    "..",
    "strava_raw.jsonl"
)


def write_raw(activities: List[Dict]) -> None:
    """
    Append-only zapis RAW danych Stravy.

    Zakładamy:
    - activities to TYLKO nowe aktywności
    - każda aktywność to dict z API
    """

    if not activities:
        return

    os.makedirs(os.path.dirname(RAW_FILE), exist_ok=True)

    with open(RAW_FILE, "a", encoding="utf-8") as f:
        for activity in activities:
            row = {
                "activity_id": int(activity["id"]),
                "start_date": activity["start_date"],
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "raw_json": activity,
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

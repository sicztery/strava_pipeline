import json
import logging
import uuid
from datetime import datetime, timezone
from google.cloud import storage

from app.auth.auth_client import get_access_token
from app.state.state_manager import load_state, save_state
from app.api.strava_api import fetch_activities
from app.ingest.filter import (
    filter_new_activities,
    extract_new_state
)
from app.ingest.raw_writer import write_raw
from app.staging.transformer import transform_activity
from app.staging.writer import write_staging



# ======================
# LOGGING SETUP
# ======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("strava_pipeline")


def log_event(
    run_id: str,
    step: str,
    status: str,
    message: str,
    extra: dict | None = None
):
    parts = [
        run_id,
        step,
        status,
        message
    ]

    if extra:
        extra_str = " | ".join(
            f"{k}={v}" for k, v in extra.items()
        )
        parts.append(extra_str)

    logger.info(" | ".join(parts))



def main():
    run_id = str(uuid.uuid4())[:8]

    log_event(
        run_id,
        step="PIPELINE_START",
        status="OK",
        message="Pipeline run started"
    )
        
    try:
        # ======================
        # 1️⃣ AUTH
        # ======================
        log_event(run_id, "AUTH", "START", "Requesting access token")
        access_token = get_access_token()
        log_event(run_id, "AUTH", "OK", "Access token obtained")

        # ======================
        # 2️⃣ LOAD STATE
        # ======================
        log_event(run_id, "STATE_LOAD", "START", "Loading last state")
        last_seen_timestamp, last_seen_activity_id = load_state()

        log_event(
            run_id,
            "STATE_LOAD",
            "OK",
            "State loaded",
            {
                "last_seen_timestamp": last_seen_timestamp,
                "last_seen_activity_id": last_seen_activity_id,
            }
        )

        # ======================
        # 3️⃣ FETCH FROM STRAVA
        # ======================
        log_event(
            run_id,
            "FETCH_API",
            "START",
            "Fetching activities from Strava",
            {"after_timestamp": last_seen_timestamp}
        )

        activities = fetch_activities(
            access_token=access_token,
            after_timestamp=last_seen_timestamp
        )

        log_event(
            run_id,
            "FETCH_API",
            "OK",
            "Activities fetched",
            {"fetched_count": len(activities)}
        )

        if not activities:
            log_event(
                run_id,
                "PIPELINE_END",
                "OK",
                "No new activities returned by API – nothing to process"
            )
            return
     


        # ======================
        # 4️⃣ FILTER NEW
        # ======================
        log_event(run_id, "FILTER", "START", "Filtering new activities")

        new_activities = filter_new_activities(
            activities=activities,
            last_seen_timestamp=last_seen_timestamp,
            last_seen_activity_id=last_seen_activity_id
        )

        log_event(
            run_id,
            "FILTER",
            "OK",
            "Filtering completed",
            {"new_count": len(new_activities)}
        )

        if not new_activities:
            log_event(
                run_id,
                "PIPELINE_END",
                "OK",
                "No new activities after filtering"
            )
            return

        logger.info("Zapis do GCS zakończony powodzeniem")
        

        # ======================
        # 5️⃣ SORT
        # ======================
        log_event(run_id, "SORT", "START", "Sorting activities deterministically")

        new_activities_sorted = sorted(
            new_activities,
            key=lambda a: (
                a["start_date"],
                int(a["id"])
            )
        )

        log_event(
            run_id,
            "SORT",
            "OK",
            "Sorting completed"
        )

        # ======================
        # 6️⃣ WRITE RAW
        # ======================
        log_event(
            run_id,
            "WRITE_RAW",
            "START",
            "Writing RAW activities",
            {"records": len(new_activities_sorted)}
        )

        write_raw(new_activities_sorted)

        log_event(
            run_id,
            "WRITE_RAW",
            "OK",
            "RAW write completed"
        )

        # ======================
        # 7️⃣ UPDATE STATE
        # ======================
        log_event(run_id, "STATE_UPDATE", "START", "Updating state")

        new_timestamp, new_activity_id = extract_new_state(
            new_activities_sorted
        )

        save_state(new_timestamp, new_activity_id)

        log_event(
            run_id,
            "STATE_UPDATE",
            "OK",
            "State updated",
            {
                "new_timestamp": new_timestamp,
                "new_activity_id": new_activity_id
            }
        )

        log_event(
            run_id,
            "PIPELINE_END",
            "OK",
            "Pipeline run finished successfully"
        )
        # ======================
        # 8️⃣ STAGING (DERIVED)
        # ======================
        log_event(
            run_id,
            "STAGING",
            "START",
            "Writing STAGING records"
        )

        staging_activities = [
            transform_activity(a) for a in new_activities_sorted
        ]

        write_staging(staging_activities)

        log_event(
            run_id,
            "STAGING",
            "OK",
            "STAGING write completed",
            {"records": len(staging_activities)}
        )

    except Exception as e:
        log_event(
            run_id,
            "PIPELINE_ERROR",
            "FAIL",
            "Pipeline failed with exception",
            {"error": str(e)}
        )
        raise

def write_single_activity_to_gcs(activity: dict):
    bucket_name = "strava-raw-alpine-proton-482413"
    
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # prosty, czytelny path RAW
    today = datetime.utcnow().strftime("%Y/%m/%d")
    blob_path = f"raw/strava/{today}/activities.jsonl"

    blob = bucket.blob(blob_path)
    


    # zapis append-only (jsonl)
    blob.upload_from_string(
        json.dumps(activity) + "\n",
        content_type="application/json"
    )
   

if __name__ == "__main__":
    main()

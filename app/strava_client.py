import logging
import uuid

from app.api.strava_api import fetch_activities
from app.auth.auth_client import get_access_token
from app.ingest.filter import extract_new_state, filter_new_activities
from app.ingest.raw_writer import write_raw
from app.state.state_manager import load_state, save_state
from app.staging.query_trigger import execute_pipeline_query
from app.staging.stage_writer import write_staging
from app.staging.transformer import transform_activity


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("strava_pipeline")


def log_event(
    run_id: str,
    step: str,
    status: str,
    message: str,
    extra: dict | None = None,
):
    parts = [run_id, step, status, message]

    if extra:
        extra_str = " | ".join(f"{k}={v}" for k, v in extra.items())
        parts.append(extra_str)

    logger.info(" | ".join(parts))


def run_pipeline():
    run_id = str(uuid.uuid4())[:8]

    log_event(
        run_id,
        step="PIPELINE_START",
        status="OK",
        message="Pipeline run started",
    )

    try:
        log_event(run_id, "AUTH", "START", "Requesting access token")
        access_token = get_access_token()
        log_event(run_id, "AUTH", "OK", "Access token obtained")

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
            },
        )

        log_event(
            run_id,
            "FETCH_API",
            "START",
            "Fetching activities from Strava",
            {"after_timestamp": last_seen_timestamp},
        )

        activities = fetch_activities(
            access_token=access_token,
            after_timestamp=last_seen_timestamp,
        )

        log_event(
            run_id,
            "FETCH_API",
            "OK",
            "Activities fetched",
            {"fetched_count": len(activities)},
        )

        if not activities:
            log_event(
                run_id,
                "PIPELINE_END",
                "OK",
                "No new activities returned by API - nothing to process",
            )
            return

        log_event(run_id, "FILTER", "START", "Filtering new activities")

        new_activities = filter_new_activities(
            activities=activities,
            last_seen_timestamp=last_seen_timestamp,
            last_seen_activity_id=last_seen_activity_id,
        )

        log_event(
            run_id,
            "FILTER",
            "OK",
            "Filtering completed",
            {"new_count": len(new_activities)},
        )

        if not new_activities:
            log_event(
                run_id,
                "PIPELINE_END",
                "OK",
                "No new activities after filtering",
            )
            return

        log_event(run_id, "SORT", "START", "Sorting activities deterministically")

        new_activities_sorted = sorted(
            new_activities,
            key=lambda activity: (activity["start_date"], int(activity["id"])),
        )

        log_event(run_id, "SORT", "OK", "Sorting completed")

        log_event(
            run_id,
            "WRITE_RAW",
            "START",
            "Writing RAW activities",
            {"records": len(new_activities_sorted)},
        )

        write_raw(new_activities_sorted, run_id)

        log_event(run_id, "WRITE_RAW", "OK", "RAW write completed")

        log_event(run_id, "STAGING", "START", "Writing STAGING records")

        staging_activities = [
            staged
            for staged in (
                transform_activity(activity) for activity in new_activities_sorted
            )
            if staged is not None
        ]

        if not staging_activities:
            log_event(
                run_id,
                "STAGING",
                "SKIP",
                "No staging records after transform",
            )
        else:
            write_staging(staging_activities, run_id)
            log_event(
                run_id,
                "STAGING",
                "OK",
                "STAGING write completed",
                {"records": len(staging_activities)},
            )

        # Advance the checkpoint only after the Athena step succeeds.
        execute_pipeline_query(run_id)

        log_event(run_id, "STATE_UPDATE", "START", "Updating state")

        new_timestamp, new_activity_id = extract_new_state(new_activities_sorted)
        save_state(new_timestamp, new_activity_id)

        log_event(
            run_id,
            "STATE_UPDATE",
            "OK",
            "State updated",
            {
                "new_timestamp": new_timestamp,
                "new_activity_id": new_activity_id,
            },
        )

        log_event(
            run_id,
            "PIPELINE_END",
            "OK",
            "Pipeline run finished successfully",
        )

    except Exception as exc:
        log_event(
            run_id,
            "PIPELINE_ERROR",
            "FAIL",
            "Pipeline failed with exception",
            {"error": str(exc)},
        )
        raise


if __name__ == "__main__":
    run_pipeline()

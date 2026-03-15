from datetime import datetime
from typing import List, Dict, Tuple


def _to_timestamp(start_date: str) -> int:
    """
    Converts ISO 8601 (Strava start_date) to UTC timestamp (int).
    """
    return int(
        datetime.fromisoformat(
            start_date.replace("Z", "+00:00")
        ).timestamp()
    )


def filter_new_activities(
    activities: List[Dict],
    last_seen_timestamp: int | None,
    last_seen_activity_id: int | None
) -> List[Dict]:
    """
    Returns ONLY new activities according to ingestion contract.

    Does not write anything.
    Does not sort final results (orchestrator does that).
    """

    # first run / no state → all activities are new
    if last_seen_timestamp is None or last_seen_activity_id is None:
        return activities

    new_activities = []

    for activity in activities:
        if "start_date" not in activity or "id" not in activity:
            # skip malformed data
            continue

        activity_ts = _to_timestamp(activity["start_date"])
        activity_id = int(activity["id"])

        is_new = (
            activity_ts > last_seen_timestamp
            or (
                activity_ts == last_seen_timestamp
                and activity_id > last_seen_activity_id
            )
        )

        if is_new:
            new_activities.append(activity)

    return new_activities


def extract_new_state(activities: List[Dict]) -> Tuple[int, int]:
    """
    Calculates new ingestion checkpoint based on list of NEW activities.

    ASSUMES:
    - list is not empty
    - activities are SORTED in ascending order
      by (start_date, id)
    """

    last = activities[-1]

    timestamp = _to_timestamp(last["start_date"])
    activity_id = int(last["id"])

    return timestamp, activity_id


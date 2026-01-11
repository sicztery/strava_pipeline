from datetime import datetime
from typing import List, Dict, Tuple


def _to_timestamp(start_date: str) -> int:
    """
    Zamienia ISO 8601 (Strava start_date) na timestamp UTC (int).
    """
    return int(
        datetime.fromisoformat(
            start_date.replace("Z", "+00:00")
        ).timestamp()
    )


def filter_new_activities(
    activities: List[Dict],
    last_seen_timestamp: int,
    last_seen_activity_id: int
) -> List[Dict]:
    """
    Zwraca TYLKO nowe aktywności zgodnie z kontraktem ingestu.

    Nie zapisuje.
    Nie sortuje wyników końcowych (robi to orchestrator).
    """

    new_activities = []

    for activity in activities:
        if "start_date" not in activity or "id" not in activity:
            # twardo pomijamy śmieci
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
    Wylicza nowy punkt ingestu na podstawie listy NOWYCH aktywności.

    ZAKŁADAMY:
    - lista niepusta
    - aktywności są POSORTOWANE rosnąco
      po (start_date, id)
    """

    last = activities[-1]

    timestamp = _to_timestamp(last["start_date"])
    activity_id = int(last["id"])

    return timestamp, activity_id

import json
import os
from typing import Tuple

STATE_FILE = os.path.join(
    os.path.dirname(__file__),
    "state.json"
)


# ======================
# LOAD
# ======================

def load_state() -> Tuple[int, int]:
    """
    Zwraca:
        (last_seen_timestamp, last_seen_activity_id)
    """

    if not os.path.exists(STATE_FILE):
        raise RuntimeError("Brak state.json – stan ingestu nie istnieje")

    with open(STATE_FILE, "r") as f:
        data = json.load(f)

    if "last_seen_timestamp" not in data:
        raise RuntimeError("state.json nie zawiera last_seen_timestamp")

    if "last_seen_activity_id" not in data:
        raise RuntimeError("state.json nie zawiera last_seen_activity_id")

    return (
        int(data["last_seen_timestamp"]),
        int(data["last_seen_activity_id"]),
    )


# ======================
# SAVE
# ======================

def save_state(timestamp: int, activity_id: int) -> None:
    """
    Zapisuje nowy punkt ingestu.
    """

    if not isinstance(timestamp, int):
        raise ValueError("timestamp musi być int")

    if not isinstance(activity_id, int):
        raise ValueError("activity_id musi być int")

    with open(STATE_FILE, "w") as f:
        json.dump(
            {
                "last_seen_timestamp": timestamp,
                "last_seen_activity_id": activity_id,
            },
            f,
            indent=2
        )

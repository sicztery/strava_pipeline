from auth.auth_client import get_access_token
from state.state_manager import load_state, save_state
from api.strava_api import fetch_activities
from ingest.filter import (
    filter_new_activities,
    extract_new_state
)
from ingest.raw_writer import write_raw


def main():
    # ======================
    # 1️⃣ AUTH
    # ======================
    access_token = get_access_token()

    # ======================
    # 2️⃣ LOAD STATE
    # ======================
    last_seen_timestamp, last_seen_activity_id = load_state()

    print(
        "STATE:",
        last_seen_timestamp,
        last_seen_activity_id
    )

    # ======================
    # 3️⃣ FETCH FROM STRAVA
    # ======================
    activities = fetch_activities(
        access_token=access_token,
        after_timestamp=last_seen_timestamp
    )

    print("Fetched from API:", len(activities))

    if not activities:
        print("API zwróciło 0 rekordów. Kończę.")
        return

    # ======================
    # 4️⃣ FILTER NEW
    # ======================
    new_activities = filter_new_activities(
        activities=activities,
        last_seen_timestamp=last_seen_timestamp,
        last_seen_activity_id=last_seen_activity_id
    )

    print("After filter:", len(new_activities))

    if not new_activities:
        print("Brak nowych aktywności. Kończę.")
        return

    # ======================
    # 5️⃣ SORT (deterministycznie)
    # ======================
    new_activities_sorted = sorted(
        new_activities,
        key=lambda a: (
            a["start_date"],
            int(a["id"])
        )
    )

    # ======================
    # 6️⃣ WRITE RAW
    # ======================
    write_raw(new_activities_sorted)

    # ======================
    # 7️⃣ UPDATE STATE
    # ======================
    new_timestamp, new_activity_id = extract_new_state(
        new_activities_sorted
    )

    save_state(new_timestamp, new_activity_id)

    print(
        "STATE UPDATED TO:",
        new_timestamp,
        new_activity_id
    )
    print("Pipeline run OK")


if __name__ == "__main__":
    main()

def transform_activity(raw: dict) -> dict:
    return {
        "activity_id": raw["id"],
        "name": raw.get("name"),
        "sport_type": raw.get("sport_type"),

        "start_date_utc": raw.get("start_date"),
        "start_date_local": raw.get("start_date_local"),
        "utc_offset": raw.get("utc_offset"),
        "timezone": raw.get("timezone"),

        "distance_m": raw.get("distance"),
        "moving_time_s": raw.get("moving_time"),
        "elapsed_time_s": raw.get("elapsed_time"),
        "elevation_gain_m": raw.get("total_elevation_gain"),

        "average_speed_mps": raw.get("average_speed"),
        "max_speed_mps": raw.get("max_speed"),

        "average_hr": raw.get("average_heartrate"),
        "max_hr": raw.get("max_heartrate"),
        "has_heartrate": raw.get("has_heartrate"),

        "device_name": raw.get("device_name"),

        "start_lat": raw.get("start_latlng", [None, None])[0],
        "start_lng": raw.get("start_latlng", [None, None])[1],
        "end_lat": raw.get("end_latlng", [None, None])[0],
        "end_lng": raw.get("end_latlng", [None, None])[1],

        "is_private": raw.get("private"),
        "is_commute": raw.get("commute"),
        "is_manual": raw.get("manual"),
    }

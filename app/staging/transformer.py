def _safe_latlng(value):
    if (
        isinstance(value, list)
        and len(value) == 2
    ):
        return value[0], value[1]
    return None, None


def transform_activity(raw: dict) -> dict:
    start_lat, start_lng = _safe_latlng(raw.get("start_latlng"))
    end_lat, end_lng = _safe_latlng(raw.get("end_latlng"))

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

        "start_lat": start_lat,
        "start_lng": start_lng,
        "end_lat": end_lat,
        "end_lng": end_lng,

        "is_private": raw.get("private"),
        "is_commute": raw.get("commute"),
        "is_manual": raw.get("manual"),
    }


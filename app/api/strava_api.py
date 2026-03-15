import requests
from typing import List, Dict

STRAVA_BASE_URL = "https://www.strava.com/api/v3"


def fetch_activities(
    access_token: str,
    after_timestamp: int,
    per_page: int = 200,
    page: int = 1
) -> List[Dict]:
    """
    Fetches activities from Strava API.

    WARNING:
    - Does NOT guarantee order
    - Does NOT filter by time
    - after_timestamp is just a hint to the API
    """

    if not access_token:
        raise ValueError("Missing access_token")

    response = requests.get(
        f"{STRAVA_BASE_URL}/athlete/activities",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        params={
            "after": after_timestamp,
            "per_page": per_page,
            "page": page
        },
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise RuntimeError("Unexpected response format from Strava")

    return data

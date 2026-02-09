import os
import requests
import logging
import json

from app.secrets import get_secret, update_refresh_token_if_changed


PROJECT_ID = os.getenv("STRAVA_GCP_PROJECT")
if not PROJECT_ID:
    raise RuntimeError("Missing env var: STRAVA_GCP_PROJECT")

CLIENT_ID = get_secret("strava-client-id", PROJECT_ID)
CLIENT_SECRET = get_secret("strava-client-secret", PROJECT_ID)

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"

logger = logging.getLogger("strava_pipeline")


def get_access_token() -> str:
    refresh_state = get_secret("strava-auth-state", PROJECT_ID)
    refresh_token = json.loads(refresh_state)["refresh_token"]

    response = requests.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": CLIENT_ID,          # string
            "client_secret": CLIENT_SECRET,  # string
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=10
    )

    response.raise_for_status()
    data = response.json()

    if "refresh_token" in data:
        updated = update_refresh_token_if_changed(
            secret_name="strava-auth-state",
            project_id=PROJECT_ID,
            new_refresh_token=data["refresh_token"]
        )

        if updated:
            logger.info("Refresh token rotated and stored in Secret Manager")

    if "access_token" not in data:
        raise RuntimeError("Brak access_token w odpowiedzi Stravy")

    return data["access_token"]






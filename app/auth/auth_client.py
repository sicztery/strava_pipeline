import os
import requests
import logging

from app.secrets import get_json_secret, update_json_secret_if_changed

logger = logging.getLogger("strava_pipeline")

PROJECT_ID = os.getenv("STRAVA_GCP_PROJECT")
if not PROJECT_ID:
    raise RuntimeError("Missing env var: STRAVA_GCP_PROJECT")

CLIENT_ID = get_json_secret("strava-client-id", PROJECT_ID)["client_id"]
CLIENT_SECRET = get_json_secret("strava-client-secret", PROJECT_ID)["client_secret"]

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
AUTH_STATE_SECRET = "strava-auth-state"


def get_access_token() -> str:
    auth_state = get_json_secret(AUTH_STATE_SECRET, PROJECT_ID)
    refresh_token = auth_state.get("refresh_token")

    if not refresh_token:
        raise RuntimeError("Brak refresh_token w auth_state – wymagany bootstrap OAuth")

    response = requests.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=10
    )

    response.raise_for_status()
    data = response.json()

    if "refresh_token" in data:
        updated = update_json_secret_if_changed(
            secret_name=AUTH_STATE_SECRET,
            project_id=PROJECT_ID,
            new_payload={"refresh_token": data["refresh_token"]}
        )

        if updated:
            logger.info("AUTH_STATE: refresh token rotated and saved")

    if "access_token" not in data:
        raise RuntimeError("Brak access_token w odpowiedzi Stravy")

    return data["access_token"]

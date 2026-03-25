import os
import requests
import logging
import json

from app.aws_secrets import get_secret, update_refresh_token_if_changed


SECRET_PREFIX = os.getenv("SECRET_PREFIX", "strava")
CLIENT_ID_SECRET = os.getenv("STRAVA_CLIENT_ID_SECRET", f"{SECRET_PREFIX}-client-id")
CLIENT_SECRET_SECRET = os.getenv("STRAVA_CLIENT_SECRET_SECRET", f"{SECRET_PREFIX}-client-secret")
AUTH_STATE_SECRET = os.getenv("STRAVA_AUTH_STATE_SECRET", f"{SECRET_PREFIX}-auth-state")

CLIENT_ID = get_secret(CLIENT_ID_SECRET)
CLIENT_SECRET = get_secret(CLIENT_SECRET_SECRET)

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"

logger = logging.getLogger("strava_pipeline")


def _extract_refresh_token(raw_value: str) -> str:
    try:
        data = json.loads(raw_value)
    except json.JSONDecodeError:
        token = raw_value.strip()
        if not token:
            raise RuntimeError("Empty refresh token in auth state secret")
        logger.warning(
            "Auth state secret is not JSON; using raw value as refresh token"
        )
        return token

    if isinstance(data, dict) and "refresh_token" in data:
        return data["refresh_token"]

    if isinstance(data, str):
        # Handle double-encoded JSON or a raw token string
        try:
            nested = json.loads(data)
            if isinstance(nested, dict) and "refresh_token" in nested:
                return nested["refresh_token"]
        except json.JSONDecodeError:
            token = data.strip()
            if token:
                logger.warning(
                    "Auth state secret is a string; using it as refresh token"
                )
                return token

    raise RuntimeError(
        "Auth state secret must be JSON with refresh_token or a raw token string"
    )


def get_access_token() -> str:
    refresh_state = get_secret(AUTH_STATE_SECRET)
    refresh_token = _extract_refresh_token(refresh_state)

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
            secret_name=AUTH_STATE_SECRET,
            new_refresh_token=data["refresh_token"]
        )

        if updated:
            logger.info("Refresh token rotated and stored in Secret Manager")

    if "access_token" not in data:
        raise RuntimeError("Missing access_token in Strava response")

    return data["access_token"]






import json
import os
import requests
import logging
from google.cloud import secretmanager
from google.api_core.exceptions import NotFound

from app.secrets import get_secret

logger = logging.getLogger("strava_pipeline")

# ======================
# KONFIGURACJA
# ======================

PROJECT_ID = os.getenv("STRAVA_GCP_PROJECT")
if not PROJECT_ID:
    raise RuntimeError("Missing env var: STRAVA_GCP_PROJECT")

CLIENT_ID = get_secret("strava-client-id", PROJECT_ID)
CLIENT_SECRET = get_secret("strava-client-secret", PROJECT_ID)

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"

# 🔑 AUTH STATE (SECRET MANAGER)
AUTH_STATE_SECRET = f"projects/{PROJECT_ID}/secrets/strava-auth-state"

# ======================
# SECRET MANAGER IO
# ======================

def _load_refresh_token() -> str | None:
    client = secretmanager.SecretManagerServiceClient()

    try:
        response = client.access_secret_version(
            request={
                "name": f"{AUTH_STATE_SECRET}/versions/latest"
            }
        )
    except NotFound:
        logger.info("AUTH_STATE: secret not found (bootstrap required)")
        return None

    payload = response.payload.data.decode("utf-8")
    data = json.loads(payload)

    return data.get("refresh_token")


def _save_refresh_token(refresh_token: str) -> None:
    client = secretmanager.SecretManagerServiceClient()

    payload = json.dumps(
        {"refresh_token": refresh_token}
    ).encode("utf-8")

    client.add_secret_version(
        request={
            "parent": AUTH_STATE_SECRET,
            "payload": {"data": payload},
        }
    )

    logger.info("AUTH_STATE: new secret version created")

# ======================
# API MODUŁU (KONTRAKT)
# ======================

def get_access_token() -> str:
    """
    Zwraca zawsze aktualny access token.
    Refresh token jest automatycznie rotowany
    i zapisywany jako NOWA WERSJA secreta.
    """

    refresh_token = _load_refresh_token()

    if not refresh_token:
        raise RuntimeError(
            "Brak refresh_token w Secret Manager – "
            "wymagany jednorazowy OAuth bootstrap"
        )

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

    # 🔁 Strava ZAWSZE rotuje refresh_token
    if "refresh_token" in data:
        _save_refresh_token(data["refresh_token"])

    if "access_token" not in data:
        raise RuntimeError("Brak access_token w odpowiedzi Stravy")

    return data["access_token"]

import json
import os
import requests
import logging
from google.cloud.parameter_manager_v1 import ParameterManagerClient
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

AUTH_PARAMETER = (
    "projects/alpine-proton-482413-u0/"
    "locations/europe-west1/"
    "parameters/auth_state"
)

# ======================
# PARAMETER MANAGER IO
# ======================

def _load_refresh_token() -> str | None:
    client = ParameterManagerClient()

    try:
        response = client.access_parameter_version(
            name=f"{AUTH_PARAMETER}/versions/latest"
        )
    except NotFound:
        logger.info("AUTH_STATE: parameter not found (bootstrap required)")
        return None

    payload = response.payload.data.decode("utf-8")
    data = json.loads(payload)

    return data.get("refresh_token")


def _save_refresh_token(refresh_token: str) -> None:
    client = ParameterManagerClient()

    payload = json.dumps(
        {"refresh_token": refresh_token}
    ).encode("utf-8")

    client.create_parameter_version(
        parent=AUTH_PARAMETER,
        parameter_version={
            "payload": {"data": payload}
        }
    )

    logger.info("AUTH_STATE: new parameter version created")

# ======================
# API MODUŁU
# ======================

def get_access_token() -> str:
    refresh_token = _load_refresh_token()

    if not refresh_token:
        raise RuntimeError(
            "Brak refresh_token w Parameter Manager – "
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

    # 🔁 Strava ZAWSZE zwraca nowy refresh_token
    if "refresh_token" in data:
        _save_refresh_token(data["refresh_token"])

    if "access_token" not in data:
        raise RuntimeError("Brak access_token w odpowiedzi Stravy")

    return data["access_token"]

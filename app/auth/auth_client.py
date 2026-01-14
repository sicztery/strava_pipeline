import json
import os
import requests
from pathlib import Path

from app.secrets import get_secret

# ======================
# KONFIGURACJA
# ======================

PROJECT_ID = os.getenv("STRAVA_GCP_PROJECT")
if not PROJECT_ID:
    raise RuntimeError("Missing env var: STRAVA_GCP_PROJECT")

CLIENT_ID = get_secret("strava-client-id", PROJECT_ID)
CLIENT_SECRET = get_secret("strava-client-secret", PROJECT_ID)

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"

AUTH_STATE_FILE = Path(__file__).parent / "auth_state.json"

# ======================
# POMOCNICZE
# ======================

def _load_refresh_token() -> str:
    if not AUTH_STATE_FILE.exists():
        raise RuntimeError("Brak auth_state.json z refresh tokenem")

    with open(AUTH_STATE_FILE, "r") as f:
        data = json.load(f)

    if "refresh_token" not in data:
        raise RuntimeError("auth_state.json nie zawiera refresh_token")

    return data["refresh_token"]


def _save_refresh_token(refresh_token: str) -> None:
    with open(AUTH_STATE_FILE, "w") as f:
        json.dump(
            {"refresh_token": refresh_token},
            f,
            indent=2
        )

# ======================
# API MODUŁU (KONTRAKT)
# ======================

def get_access_token() -> str:
    """
    Zwraca zawsze aktualny access token.
    Refresh token jest automatycznie rotowany i zapisywany lokalnie.
    """

    refresh_token = _load_refresh_token()

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

    # 🔁 OAuth Stravy ZAWSZE zwraca nowy refresh token
    if "refresh_token" in data:
        _save_refresh_token(data["refresh_token"])

    if "access_token" not in data:
        raise RuntimeError("Brak access_token w odpowiedzi Stravy")

    return data["access_token"]



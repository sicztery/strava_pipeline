import json
import os
import requests

# ======================
# KONFIGURACJA
# ======================

CLIENT_ID = "194342"
CLIENT_SECRET = "5c0df3e2a5475d158b6967e237de0d06bb6eba3d"

AUTH_STATE_FILE = os.path.join(
    os.path.dirname(__file__),
    "auth_state.json"
)

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"


# ======================
# POMOCNICZE
# ======================

def _load_refresh_token() -> str:
    if not os.path.exists(AUTH_STATE_FILE):
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
    Refresh token jest automatycznie rotowany i zapisywany.
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

    # 🔑 ZAWSZE zapisujemy refresh token z odpowiedzi
    if "refresh_token" in data:
        _save_refresh_token(data["refresh_token"])

    if "access_token" not in data:
        raise RuntimeError("Brak access_token w odpowiedzi Stravy")

    return data["access_token"]


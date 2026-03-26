import os
import logging
import requests
from dotenv import load_dotenv
from app.aws_secrets import get_secret

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("strava_pipeline")

SECRET_PREFIX = os.getenv("SECRET_PREFIX", "strava")
CLIENT_ID_SECRET = os.getenv(
    "STRAVA_CLIENT_ID_SECRET",
    f"{SECRET_PREFIX}-client-id"
)
CLIENT_SECRET_SECRET = os.getenv(
    "STRAVA_CLIENT_SECRET_SECRET",
    f"{SECRET_PREFIX}-client-secret"
)
WEBHOOK_VERIFY_TOKEN_SECRET = os.getenv(
    "WEBHOOK_VERIFY_TOKEN_SECRET",
    f"{SECRET_PREFIX}-webhook-verify-token"
)

BASE_URL = "https://www.strava.com/api/v3/push_subscriptions"


def _load_config():
    verify_token = os.getenv("WEBHOOK_VERIFY_TOKEN")
    if not verify_token:
        try:
            verify_token = get_secret(WEBHOOK_VERIFY_TOKEN_SECRET)
        except Exception as e:
            raise RuntimeError(
                "Missing env var: WEBHOOK_VERIFY_TOKEN"
            ) from e

    callback_url = os.getenv("WEBHOOK_CALLBACK_URL")
    if not callback_url:
        raise RuntimeError("Missing env var: WEBHOOK_CALLBACK_URL")

    client_id = get_secret(CLIENT_ID_SECRET)
    client_secret = get_secret(CLIENT_SECRET_SECRET)

    return client_id, client_secret, verify_token, callback_url


def list_subscriptions(client_id: str, client_secret: str):
    r = requests.get(
        BASE_URL,
        params={
            "client_id": client_id,
            "client_secret": client_secret,
        }
    )
    r.raise_for_status()
    return r.json()


def delete_subscription(sub_id: int, client_id: str, client_secret: str):
    logger.info(f"Deleting existing subscription: {sub_id}")

    r = requests.delete(
        f"{BASE_URL}/{sub_id}",
        params={
            "client_id": client_id,
            "client_secret": client_secret,
        }
    )

    r.raise_for_status()


def create_subscription():
    client_id, client_secret, verify_token, callback_url = _load_config()

    logger.info("Checking existing subscriptions")

    subs = list_subscriptions(client_id, client_secret)

    if subs:
        for sub in subs:
            delete_subscription(sub.get("id"), client_id, client_secret)

    logger.info("Creating new Strava webhook subscription")

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "callback_url": callback_url,
        "verify_token": verify_token,
    }

    r = requests.post(BASE_URL, data=payload, timeout=30)

    logger.info(f"Status: {r.status_code}")
    logger.info(f"Response JSON: {r.json()}")

    r.raise_for_status()

    logger.info("Webhook subscription created successfully")

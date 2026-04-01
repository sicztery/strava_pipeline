import os
import logging
import time
import requests
from app.aws_secrets import get_secret
from app.runtime_env import load_local_dotenv

load_local_dotenv()

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
PREFLIGHT_CHALLENGE = "strava-preflight-challenge"


def _load_config():
    verify_token = os.getenv("WEBHOOK_VERIFY_TOKEN")
    verify_token_source = "env"
    if not verify_token:
        try:
            verify_token = get_secret(WEBHOOK_VERIFY_TOKEN_SECRET)
            verify_token_source = "secretsmanager"
        except Exception as e:
            raise RuntimeError(
                "Missing env var: WEBHOOK_VERIFY_TOKEN"
            ) from e

    callback_url = os.getenv("WEBHOOK_CALLBACK_URL")
    if not callback_url:
        raise RuntimeError("Missing env var: WEBHOOK_CALLBACK_URL")

    client_id = get_secret(CLIENT_ID_SECRET)
    client_secret = get_secret(CLIENT_SECRET_SECRET)

    logger.info("Using webhook verify token from %s", verify_token_source)
    logger.info("Using callback URL: %s", callback_url)

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


def verify_callback(callback_url: str, verify_token: str, timeout: int = 5):
    started_at = time.perf_counter()

    response = requests.get(
        callback_url,
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": verify_token,
            "hub.challenge": PREFLIGHT_CHALLENGE,
        },
        timeout=timeout,
    )

    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 1)
    logger.info(
        "Callback preflight completed with status=%s in %sms",
        response.status_code,
        elapsed_ms,
    )

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Callback preflight returned non-JSON body with status {response.status_code}"
        ) from exc

    if response.status_code != 200:
        raise RuntimeError(
            f"Callback preflight failed with status {response.status_code}: {payload}"
        )

    if payload.get("hub.challenge") != PREFLIGHT_CHALLENGE:
        raise RuntimeError(
            f"Callback preflight returned unexpected challenge payload: {payload}"
        )

    logger.info("Callback preflight succeeded")


def create_subscription():
    client_id, client_secret, verify_token, callback_url = _load_config()

    logger.info("Checking existing subscriptions")

    subs = list_subscriptions(client_id, client_secret)

    for sub in subs:
        if sub.get("callback_url") == callback_url:
            logger.info(
                "Subscription already exists for callback URL: id=%s",
                sub.get("id"),
            )
            return

    verify_callback(callback_url, verify_token)

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

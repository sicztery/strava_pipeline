import os
import logging
import requests
from dotenv import load_dotenv
from app.gcp_secrets import get_secret

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("strava_pipeline")

PROJECT_ID = os.getenv("STRAVA_GCP_PROJECT")
if not PROJECT_ID:
    raise RuntimeError("Missing env var: STRAVA_GCP_PROJECT")

VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN")
if not VERIFY_TOKEN:
    raise RuntimeError("Missing env var: WEBHOOK_VERIFY_TOKEN")

CALLBACK_URL = os.getenv("WEBHOOK_CALLBACK_URL")
if not CALLBACK_URL:
    raise RuntimeError("Missing env var: WEBHOOK_CALLBACK_URL")

CLIENT_ID = get_secret("strava-client-id", PROJECT_ID)
CLIENT_SECRET = get_secret("strava-client-secret", PROJECT_ID)

BASE_URL = "https://www.strava.com/api/v3/push_subscriptions"


def list_subscriptions():
    r = requests.get(
        BASE_URL,
        params={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }
    )
    r.raise_for_status()
    return r.json()


def delete_subscription(sub_id):
    logger.info(f"Deleting existing subscription: {sub_id}")

    r = requests.delete(
        f"{BASE_URL}/{sub_id}",
        params={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }
    )

    r.raise_for_status()


def create_subscription():

    logger.info("Checking existing subscriptions")

    subs = list_subscriptions()

    if subs:
        for sub in subs:
            delete_subscription(sub.get("id"))

    logger.info("Creating new Strava webhook subscription")

    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "callback_url": CALLBACK_URL,
        "verify_token": VERIFY_TOKEN,
    }

    r = requests.post(BASE_URL, data=payload, timeout=30)

    logger.info(f"Status: {r.status_code}")
    logger.info(f"Response JSON: {r.json()}")

    r.raise_for_status()

    logger.info("Webhook subscription created successfully")
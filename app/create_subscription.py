import os
import requests
import logging
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
CALLBACK_URL = os.getenv("WEBHOOK_CALLBACK_URL")
CLIENT_ID = get_secret("strava-client-id", PROJECT_ID)
CLIENT_SECRET = get_secret("strava-client-secret", PROJECT_ID)

CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")


def create_subscription():

    url = "https://www.strava.com/api/v3/push_subscriptions"

    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "callback_url": CALLBACK_URL,
        "verify_token": VERIFY_TOKEN,
    }

    logger.info("Creating Strava webhook subscription")

    response = requests.post(url, data=payload)

    logger.info(f"Status: {response.status_code}")
    logger.info(f"Response: {response.text}")

    response.raise_for_status()

    logger.info("Subscription created successfully")


if __name__ == "__main__":
    create_subscription()
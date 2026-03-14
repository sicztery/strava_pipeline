import sys

from app.webhook import run_webhook
from app.create_subscription import create_subscription
from app.strava_client import run_pipeline
from app.sql_trigger import run_transform
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("entrypoint")


def main():

    mode = sys.argv[1] if len(sys.argv) > 1 else "worker"
    logger.info(f"Starting mode: {mode}")

    if mode == "webhook":
        run_webhook()

    elif mode == "worker":
        run_pipeline()

    elif mode == "create_sub":
        create_subscription() 

    elif mode == "sql_trigger":
        run_transform()     

    else:
        raise ValueError(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
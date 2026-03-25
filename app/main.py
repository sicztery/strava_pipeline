import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("entrypoint")


def main():

    mode = sys.argv[1] if len(sys.argv) > 1 else "worker"
    logger.info(f"Starting mode: {mode}")

    if mode == "webhook":
        from app.webhook import run_webhook
        run_webhook()

    elif mode == "worker":
        from app.strava_client import run_pipeline
        run_pipeline()

    elif mode == "create_sub":
        from app.create_subscription import create_subscription
        create_subscription()

    else:
        raise ValueError(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()

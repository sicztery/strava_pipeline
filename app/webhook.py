from flask import Flask, request, jsonify
from dotenv import load_dotenv
from google.cloud import run_v2
import os
import logging
import time

# ======================
# ENV
# ======================

load_dotenv()

VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN")
PROJECT_ID = os.getenv("STRAVA_GCP_PROJECT")
REGION = os.getenv("STRAVA_GCP_REGION", "europe-west1")
JOB_NAME = os.getenv("STRAVA_WORKER_JOB")
WEBHOOK_COOLDOWN_SECONDS = int(os.getenv("WEBHOOK_COOLDOWN_SECONDS", "180"))

last_job_trigger = 0

# ======================
# LOGGING
# ======================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("strava_pipeline")

logger.info(
    f"Webhook service starting - Cloud Run trigger enabled for job: {JOB_NAME}"
)

# ======================
# APP
# ======================

app = Flask(__name__)

# ======================
# VERIFICATION
# ======================

@app.route("/webhook", methods=["GET"])
def handle_verification():

    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    logger.info(f"mode={mode}")
    logger.info("Webhook verification request received")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return jsonify({"hub.challenge": challenge}), 200

    return "Forbidden", 403


# ======================
# EVENT
# ======================

@app.route("/webhook", methods=["POST"])
def handle_event():
    global last_job_trigger
    
    event = request.json
    if not event:
        logger.warning("Empty event payload")
        return "invalid", 400

    if event.get("aspect_type") != "create":
        logger.info("Ignoring non-create event")
        return "ignored", 200
    
    if event.get("object_type") != "activity":
        logger.info("Ignoring non-activity object")
        return "ignored", 200

    logger.info(
        f"Strava event: type={event.get('aspect_type')} "
        f"object={event.get('object_type')} "
        f"id={event.get('object_id')}"
    )

    # Trigger Cloud Run job z cooldown
    now = time.time()
    if now - last_job_trigger < WEBHOOK_COOLDOWN_SECONDS:
        logger.info(
            f"Cloud Run job trigger on cooldown – skipping "
            f"(next trigger in {WEBHOOK_COOLDOWN_SECONDS - (now - last_job_trigger):.0f}s)"
        )
        return "ok", 200
    
    try:
        last_job_trigger = now
        
        client = run_v2.JobsClient()
        job_path = f"projects/{PROJECT_ID}/locations/{REGION}/jobs/{JOB_NAME}"
        
        client.run_job(name=job_path)
        
        logger.info(
            f"Cloud Run job triggered: activity_id={event.get('object_id')} "
            f"job={JOB_NAME}"
        )
    except Exception as e:
        logger.error(
            f"Failed to trigger Cloud Run job: {str(e)}",
            exc_info=True
        )
        # Zwracamy ok mimo błędu, aby webhook nie retry'ował
        # (ew. będzie trigger na następny event)
        return "ok", 200

    return "ok", 200


# ======================
# SERVER
# ======================
def run_webhook():
    PORT = int(os.environ.get("PORT", 8080))
    
    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False
    )


if __name__ == "__main__":
    run_webhook()
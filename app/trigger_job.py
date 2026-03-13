import os
import logging
import time
from flask import Flask, request
from google.cloud import run_v2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("strava_pipeline")

PROJECT_ID = os.getenv("STRAVA_GCP_PROJECT")
REGION = os.getenv("STRAVA_GCP_REGION", "europe-west1")
JOB_NAME = os.getenv("STRAVA_WORKER_JOB")
COOLDOWN_SECONDS = 180
last_run = 0

app = Flask(__name__)


@app.route("/", methods=["POST"])
def trigger():
    if not request.headers.get("Authorization"):
        return "Unauthorized", 401
    
    global last_run

    now = time.time()

    if now - last_run < COOLDOWN_SECONDS:
        logger.info("Worker trigger cooldown active – skipping")
        return "skipped", 200
    
    last_run = now

    logger.info("PubSub message received")

    client = run_v2.JobsClient()

    job_path = f"projects/{PROJECT_ID}/locations/{REGION}/jobs/{JOB_NAME}"

    client.run_job(name=job_path)

    logger.info("Worker job started")

    return "ok", 200


def run_trigger():

    PORT = int(os.environ.get("PORT", 8080))

    app.run(host="0.0.0.0", port=PORT)
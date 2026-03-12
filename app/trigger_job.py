import os
import logging
from flask import Flask, request
from google.cloud import run_v2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("strava_pipeline")

PROJECT_ID = os.getenv("STRAVA_GCP_PROJECT")
REGION = os.getenv("STRAVA_GCP_REGION", "europe-west1")
JOB_NAME = os.getenv("STRAVA_WORKER_JOB")

app = Flask(__name__)


@app.route("/", methods=["POST"])
def trigger():

    logger.info("PubSub event received")

    client = run_v2.JobsClient()

    job_path = f"projects/{PROJECT_ID}/locations/{REGION}/jobs/{JOB_NAME}"

    client.run_job(name=job_path)

    logger.info("Worker job triggered")

    return "ok", 200
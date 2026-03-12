import os
import logging
from flask import Flask, request
from google.cloud import run_v2, JobsClient, RunJobRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("strava_pipeline")

PROJECT_ID = os.getenv("STRAVA_GCP_PROJECT")
REGION = os.getenv("STRAVA_GCP_REGION", "europe-west1")
JOB_NAME = os.getenv("STRAVA_WORKER_JOB")

app = Flask(__name__)


@app.route("/", methods=["POST"])
def trigger():

    logger.info("PubSub message received")

    client = JobsClient()

    request = RunJobRequest(
        name=job_path
    )

    job_path = f"projects/{PROJECT_ID}/locations/{REGION}/jobs/{JOB_NAME}"

    client.run_job(request=request)

    logger.info("Worker job started")

    return "ok", 200


def run_trigger():

    PORT = int(os.environ.get("PORT", 8080))

    app.run(host="0.0.0.0", port=PORT)
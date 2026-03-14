from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from google.cloud import run_v2
import os
import logging
import time
import hmac
import hashlib

from app.gcp_secrets import get_secret

# ======================
# ENV
# ======================

load_dotenv()

PROJECT_ID = os.getenv("STRAVA_GCP_PROJECT")
if not PROJECT_ID:
    raise RuntimeError("Missing env var: STRAVA_GCP_PROJECT")

# Pobierz STRAVA_CLIENT_SECRET z Google Secret Manager
# (to jest ten sam secret co w auth_client.py dla OAuth)
STRAVA_CLIENT_SECRET = get_secret("strava-client-secret", PROJECT_ID)

VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN")
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
# APP & RATE LIMITING
# ======================

app = Flask(__name__)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# ======================
# SECURITY FUNCTIONS
# ======================

def verify_strava_signature(request_body_bytes: bytes, signature: str) -> bool:
    """
    Verify Strava webhook signature using HMAC SHA256.
    
    Strava sends X-Strava-Signature: v0=<HMAC_SHA256_hex>
    HMAC is computed over (request_body + client_secret)
    """
    if not STRAVA_CLIENT_SECRET:
        logger.error("STRAVA_CLIENT_SECRET not configured!")
        return False
    
    if not signature or not signature.startswith("v0="):
        logger.warning("Invalid signature format")
        return False
    
    expected_signature = signature.split("=", 1)[1]
    
    # Compute HMAC SHA256
    computed = hmac.new(
        STRAVA_CLIENT_SECRET.encode(),
        request_body_bytes,
        hashlib.sha256
    ).hexdigest()
    
    # Timing-safe comparison to prevent timing attacks
    is_valid = hmac.compare_digest(computed, expected_signature)
    
    if not is_valid:
        logger.warning("Signature verification failed")
    
    return is_valid

# ======================
# VERIFICATION
# ======================

@app.route("/webhook", methods=["GET"])
@limiter.limit("10 per minute")  # Strict limit for verification endpoints
def handle_verification():

    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    logger.debug("Webhook verification request received")

    if mode == "subscribe" and token == VERIFY_TOKEN and challenge:
        logger.info("Webhook verification successful")
        return jsonify({"hub.challenge": challenge}), 200

    logger.warning(f"Verification failed - mode: {mode}, token_match: {token == VERIFY_TOKEN}")
    return jsonify({"error": "Forbidden"}), 403


# ======================
# EVENT
# ======================

@app.route("/webhook", methods=["POST"])
@limiter.limit("30 per minute")  # Additional stricter limit for POST
def handle_event():
    global last_job_trigger
    
    # ===== SECURITY: Verify Strava Signature =====
    signature = request.headers.get("X-Strava-Signature")
    if not signature or not verify_strava_signature(request.data, signature):
        logger.error("Webhook signature verification failed - rejecting request")
        return jsonify({"error": "Unauthorized"}), 401
    
    # ===== SECURITY: Verify Authorization Token (optional defense-in-depth) =====
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        logger.warning("Missing or invalid Authorization header")
        return jsonify({"error": "Unauthorized"}), 401
    
    provided_token = auth_header.split(" ", 1)[1]
    if not hmac.compare_digest(provided_token, VERIFY_TOKEN):
        logger.error("Authorization token validation failed")
        return jsonify({"error": "Unauthorized"}), 401
    
    # ===== VALIDATION: Parse Payload =====
    event = request.json
    if not event:
        logger.warning("Empty event payload")
        return jsonify({"error": "Bad Request"}), 400

    # ===== VALIDATION: Check Event Type =====
    aspect_type = event.get("aspect_type")
    object_type = event.get("object_type")
    object_id = event.get("object_id")
    
    if aspect_type != "create":
        logger.debug(f"Ignoring event - aspect_type: {aspect_type}")
        return jsonify({"status": "ignored"}), 200
    
    if object_type != "activity":
        logger.debug(f"Ignoring event - object_type: {object_type}")
        return jsonify({"status": "ignored"}), 200
    
    if not object_id or not isinstance(object_id, int):
        logger.warning(f"Invalid object_id: {object_id}")
        return jsonify({"error": "Bad Request"}), 400

    logger.info(
        f"Valid Strava webhook: activity_id={object_id}"
    )

    # ===== TRIGGER: Cloud Run Job with Cooldown =====
    now = time.time()
    if now - last_job_trigger < WEBHOOK_COOLDOWN_SECONDS:
        seconds_remaining = WEBHOOK_COOLDOWN_SECONDS - (now - last_job_trigger)
        logger.info(
            f"Job trigger on cooldown - skipping "
            f"(next trigger in {seconds_remaining:.0f}s)"
        )
        return jsonify({"status": "ok"}), 200
    
    try:
        last_job_trigger = now
        
        client = run_v2.JobsClient()
        job_path = f"projects/{PROJECT_ID}/locations/{REGION}/jobs/{JOB_NAME}"
        
        client.run_job(name=job_path)
        
        logger.info(
            f"Cloud Run job triggered for activity_id={object_id}"
        )
    except Exception as e:
        logger.error(
            f"Failed to trigger Cloud Run job: {type(e).__name__}",
            exc_info=True
        )
        # Return 200 to prevent Strava retries
        return jsonify({"status": "ok"}), 200

    return jsonify({"status": "ok"}), 200


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
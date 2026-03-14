from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from google.cloud import run_v2
import os
import logging
import time

# ======================
# LOGGING - MUST BE FIRST
# ======================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("strava_pipeline")

# ======================
# ENV
# ======================

load_dotenv()

PROJECT_ID = os.getenv("STRAVA_GCP_PROJECT")
if not PROJECT_ID:
    raise RuntimeError("Missing env var: STRAVA_GCP_PROJECT")

# Strava IP ranges (from https://developers.strava.com/docs/#webhooks)
# These are the IP ranges from which Strava sends webhook events
STRAVA_IP_RANGES = [
    "54.160.181.190/32",  # Observed in production
    # Add more ranges from Strava documentation as needed
]

VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN")
REGION = os.getenv("STRAVA_GCP_REGION", "europe-west1")
JOB_NAME = os.getenv("STRAVA_WORKER_JOB")
WEBHOOK_COOLDOWN_SECONDS = int(os.getenv("WEBHOOK_COOLDOWN_SECONDS", "180"))

last_job_trigger = 0

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

def ip_in_range(ip: str, cidr: str) -> bool:
    """Check if IP address is in CIDR range."""
    from ipaddress import ip_address, ip_network
    try:
        return ip_address(ip) in ip_network(cidr, strict=False)
    except ValueError:
        return False


def verify_strava_ip(request_ip: str) -> bool:
    """
    Verify that webhook request comes from Strava's IP ranges.
    Uses X-Forwarded-For header (set by Cloud Run).
    """
    if not request_ip:
        logger.error("Cannot determine request IP")
        return False
    
    # Check if IP is in Strava's whitelist
    for cidr in STRAVA_IP_RANGES:
        if ip_in_range(request_ip, cidr):
            logger.info(f"✓ IP verification passed: {request_ip}")
            return True
    
    logger.error(f"IP {request_ip} not in Strava whitelist")
    return False

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
    
    # ===== SECURITY: IP Whitelist Verification =====
    # Get the actual client IP from X-Forwarded-For header (set by Cloud Run)
    client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not client_ip:
        client_ip = request.remote_addr
    
    logger.info(f"Webhook POST from IP: {client_ip}")
    
    if not verify_strava_ip(client_ip):
        logger.error(f"Unauthorized IP: {client_ip} - rejecting request")
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
        f"✓ Valid Strava webhook: activity_id={object_id}"
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
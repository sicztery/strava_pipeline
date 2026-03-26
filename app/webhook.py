from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from app.aws_secrets import get_secret
import boto3
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

SECRET_PREFIX = os.getenv("SECRET_PREFIX", "strava")
WEBHOOK_VERIFY_TOKEN_SECRET = os.getenv(
    "WEBHOOK_VERIFY_TOKEN_SECRET",
    f"{SECRET_PREFIX}-webhook-verify-token"
)
AWS_REGION = os.getenv("AWS_REGION")
ECS_CLUSTER = os.getenv("ECS_CLUSTER")
ECS_TASK_DEFINITION = os.getenv("ECS_TASK_DEFINITION")
ECS_SUBNETS = os.getenv("ECS_SUBNETS")
ECS_SECURITY_GROUPS = os.getenv("ECS_SECURITY_GROUPS")
ECS_ASSIGN_PUBLIC_IP = os.getenv("ECS_ASSIGN_PUBLIC_IP", "ENABLED")
ECS_LAUNCH_TYPE = os.getenv("ECS_LAUNCH_TYPE", "FARGATE")
WEBHOOK_COOLDOWN_SECONDS = int(os.getenv("WEBHOOK_COOLDOWN_SECONDS", "180"))

last_job_trigger = 0

logger.info(
    "Webhook service starting - ECS trigger enabled"
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

# NOTE: Strava does not publish webhook IP ranges, and they may change without notice.
# Therefore, IP whitelisting is not a viable security mechanism.
# Security is provided through:
# 1. GET endpoint token verification (verify_token in callback URL validation)
# 2. Rate limiting on POST endpoint (30 requests/minute per IP, 200/day global)
# 3. Strict payload validation (aspect_type, object_type, object_id)
# 4. HTTPS only (enforced by ALB if configured)


def _get_verify_token() -> str | None:
    token = os.getenv("WEBHOOK_VERIFY_TOKEN")
    if token:
        return token
    try:
        return get_secret(WEBHOOK_VERIFY_TOKEN_SECRET)
    except Exception:
        logger.warning(
            "Webhook verify token is missing and could not be "
            "loaded from Secrets Manager"
        )
        return None

# ======================
# VERIFICATION
# ======================

@app.route("/webhook", methods=["GET"])
@limiter.limit("10 per minute")  # Strict limit for verification endpoints
def handle_verification():

    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    verify_token = _get_verify_token()

    logger.debug("Webhook verification request received")

    if not verify_token:
        return jsonify({"error": "Server misconfigured"}), 500

    if mode == "subscribe" and token == verify_token and challenge:
        logger.info("Webhook verification successful")
        return jsonify({"hub.challenge": challenge}), 200

    logger.warning(
        f"Verification failed - mode: {mode}, token_match: {token == verify_token}"
    )
    return jsonify({"error": "Forbidden"}), 403


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok"}), 200


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

    # ===== TRIGGER: Job with Cooldown =====

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

        if not ECS_CLUSTER:
            raise RuntimeError("Missing env var: ECS_CLUSTER")
        if not ECS_TASK_DEFINITION:
            raise RuntimeError("Missing env var: ECS_TASK_DEFINITION")
        if not ECS_SUBNETS:
            raise RuntimeError("Missing env var: ECS_SUBNETS")
        if not ECS_SECURITY_GROUPS:
            raise RuntimeError("Missing env var: ECS_SECURITY_GROUPS")

        subnets = [s.strip() for s in ECS_SUBNETS.split(",") if s.strip()]
        security_groups = [
            s.strip() for s in ECS_SECURITY_GROUPS.split(",") if s.strip()
        ]

        if AWS_REGION:
            client = boto3.client("ecs", region_name=AWS_REGION)
        else:
            client = boto3.client("ecs")

        client.run_task(
            cluster=ECS_CLUSTER,
            taskDefinition=ECS_TASK_DEFINITION,
            launchType=ECS_LAUNCH_TYPE,
            count=1,
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": subnets,
                    "securityGroups": security_groups,
                    "assignPublicIp": ECS_ASSIGN_PUBLIC_IP,
                }
            },
        )

        logger.info(
            f"ECS task triggered for activity_id={object_id}"
        )
    except Exception as e:
        logger.error(
            f"Failed to trigger ECS task: {type(e).__name__}",
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

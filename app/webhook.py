from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import logging

# ======================
# ENV
# ======================

load_dotenv()

VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN")

# ======================
# LOGGING
# ======================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("strava_pipeline")

logger.info("Webhook service starting")

# ======================
# APP
# ======================

app = Flask(__name__)

# ======================
# VERIFICATION
# ======================

@app.route("/webhook", methods=["GET"])
def verify():

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
def webhook():

    event = request.json

    logger.info(f"Strava webhook event: {event}")

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
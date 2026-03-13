import os
import time
import logging
from flask import Flask, request
from google.cloud import bigquery

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("bq_transform")

app = Flask(__name__)

# ======================
# CONFIG
# ======================

PROJECT_ID = os.getenv("STRAVA_GCP_PROJECT")
DATASET = os.getenv("BQ_DATASET")
BQ_LOCATION = os.getenv("BQ_LOCATION")
COOLDOWN_SECONDS = 180
QUERY_DELAY_SECONDS = 5
last_run = 0

# Tracks recently processed message IDs to handle duplicates
# In production, consider using Redis or Datastore for distributed deployments
processed_messages = {}
MESSAGE_ID_RETENTION = 3600  # Keep message IDs for 1 hour

SQL_QUERIES = [
    "sql/pipeline_raw_buffer.sql",
    "sql/pipeline_timestamp_buffer.sql",
    "sql/pipeline_main.sql"
]

client = bigquery.Client(project=PROJECT_ID)


# ======================
# SQL LOADER
# ======================

def load_sql(path: str) -> str:

    with open(path) as f:
        sql = f.read()

    sql = sql.replace("${PROJECT_ID}", PROJECT_ID)
    sql = sql.replace("${DATASET}", DATASET)

    return sql


# ======================
# IDEMPOTENCY CHECK
# ======================

def _cleanup_old_messages():
    """Remove message IDs older than retention period."""
    now = time.time()
    expired = [
        msg_id for msg_id, timestamp in processed_messages.items()
        if now - timestamp > MESSAGE_ID_RETENTION
    ]
    for msg_id in expired:
        del processed_messages[msg_id]


def is_message_duplicate(message_id: str) -> bool:
    """Check if message was already processed."""
    _cleanup_old_messages()
    return message_id in processed_messages


def mark_message_processed(message_id: str):
    """Mark message as processed."""
    processed_messages[message_id] = time.time()


# ======================
# QUERY EXECUTION
# ======================

def run_query(sql_path: str):

    logger.info(f"Running query: {sql_path}")

    sql = load_sql(sql_path)

    job = client.query(
    sql,
    location=BQ_LOCATION
    )

    job.result()

    logger.info(f"Finished query: {sql_path}")


# ======================
# TRANSFORM PIPELINE
# ======================

def run_queries():

    for i, path in enumerate(SQL_QUERIES):

        run_query(path)

        if i < len(SQL_QUERIES) - 1:

            logger.info(
                f"Sleeping {QUERY_DELAY_SECONDS}s before next query"
            )

            time.sleep(QUERY_DELAY_SECONDS)


# ======================
# PUBSUB TRIGGER
# ======================

@app.route("/", methods=["POST"])
def trigger():

    global last_run

    # ======================
    # PARSE PUBSUB MESSAGE
    # ======================

    envelope = request.get_json()
    
    if not envelope:
        logger.error("No JSON received from Pub/Sub")
        return "Bad Request", 400

    if "message" not in envelope:
        logger.error("Invalid Pub/Sub message format - missing 'message' key")
        return "Bad Request", 400

    message = envelope["message"]
    message_id = message.get("messageId", "unknown")

    logger.info(f"Received Pub/Sub message: {message_id}")

    # ======================
    # DUPLICATE CHECK
    # ======================

    if is_message_duplicate(message_id):
        logger.info(f"Message {message_id} was already processed - skipping")
        return "ok", 200

    try:
        # ======================
        # COOLDOWN CHECK
        # ======================

        now = time.time()

        if now - last_run < COOLDOWN_SECONDS:
            logger.info(
                f"Transform cooldown active - skipping message {message_id} "
                f"({int(COOLDOWN_SECONDS - (now - last_run))}s remaining)"
            )
            # Mark as processed to avoid retry attempt even during cooldown
            mark_message_processed(message_id)
            # Return 200 to prevent Pub/Sub from retrying
            return "ok", 200

        last_run = now

        # ======================
        # EXECUTE TRANSFORM
        # ======================

        logger.info(f"Starting BigQuery transform for message {message_id}")
        run_queries()
        logger.info(f"Successfully completed transform for message {message_id}")

        # Mark as successfully processed
        mark_message_processed(message_id)

        return "ok", 200

    except Exception as e:
        logger.error(
            f"ERROR processing message {message_id}: {str(e)}", 
            exc_info=True
        )
        # Return 500 to trigger Pub/Sub retry
        return "Internal Server Error", 500


# ======================
# SERVICE ENTRYPOINT
# ======================

def run_transform():

    port = int(os.environ.get("PORT", 8080))

    logger.info("Starting BigQuery transform service")

    app.run(
        host="0.0.0.0",
        port=port
    )
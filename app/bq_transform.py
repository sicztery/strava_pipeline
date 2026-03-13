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

QUERY_DELAY_SECONDS = 5

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
# QUERY EXECUTION
# ======================

def run_query(sql_path: str):

    logger.info(f"Running query: {sql_path}")

    sql = load_sql(sql_path)

    job = client.query(sql)

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

    logger.info("Received pipeline_finished event")

    run_queries()

    return "ok", 200


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
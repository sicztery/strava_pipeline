import time
import logging
from flask import Flask, request
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bq_transform")

app = Flask(__name__)
client = bigquery.Client()

QUERY_FILES = [
    "sql/dedupe.sql",
    "sql/model.sql",
    "sql/update_view.sql"
]

QUERY_DELAY_SECONDS = 10


def run_query(sql):

    job = client.query(sql)
    job.result()

    logger.info("Query finished")


def run_queries():

    for i, path in enumerate(QUERY_FILES):

        logger.info(f"Running query: {path}")

        with open(path) as f:
            sql = f.read()

        run_query(sql)

        if i < len(QUERY_FILES) - 1:
            logger.info(f"Waiting {QUERY_DELAY_SECONDS}s before next query")
            time.sleep(QUERY_DELAY_SECONDS)


@app.route("/", methods=["POST"])
def trigger():

    logger.info("Received pipeline_finished event")

    run_queries()

    return "ok", 200


def run_transform():

    import os

    port = int(os.environ.get("PORT", 8080))

    logger.info("Starting BigQuery transform service")

    app.run(host="0.0.0.0", port=port)
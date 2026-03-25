import os
import logging
import time
import boto3

logger = logging.getLogger("strava_pipeline")


def _athena_client():
    region = os.getenv("AWS_REGION")
    if region:
        return boto3.client("athena", region_name=region)
    return boto3.client("athena")


def execute_pipeline_query(run_id: str) -> None:
    """
    Execute the pipeline query using AWS Athena.

    Set PIPELINE_QUERY_ENGINE=none to skip.
    """

    engine = os.getenv("PIPELINE_QUERY_ENGINE", "none").lower()
    if engine in ("none", "off", "false", "0"):
        logger.info(f"{run_id} | PIPELINE_QUERY | SKIP | Engine is disabled")
        return

    if engine != "athena":
        raise RuntimeError(f"Unsupported PIPELINE_QUERY_ENGINE: {engine}")

    database = os.getenv("ATHENA_DATABASE")
    output_location = os.getenv("ATHENA_OUTPUT_S3")
    workgroup = os.getenv("ATHENA_WORKGROUP")
    timeout_seconds = int(os.getenv("ATHENA_TIMEOUT_SECONDS", "300"))

    if not database:
        raise RuntimeError("Missing env var: ATHENA_DATABASE")
    if not output_location:
        raise RuntimeError("Missing env var: ATHENA_OUTPUT_S3")

    sql_path = os.getenv("PIPELINE_SQL_PATH")
    if not sql_path:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(os.path.dirname(script_dir))
        sql_path = os.path.join(base_dir, "sql/pipeline_query.sql")

    if not os.path.exists(sql_path):
        raise FileNotFoundError(f"SQL file not found: {sql_path}")

    with open(sql_path, "r") as f:
        sql_query = f.read()

    sql_query = sql_query.replace("${DATABASE}", database)
    sql_query = sql_query.replace("${DATASET}", database)

    logger.info(f"{run_id} | PIPELINE_QUERY | START | Athena query execution")

    client = _athena_client()
    params = {
        "QueryString": sql_query,
        "QueryExecutionContext": {"Database": database},
        "ResultConfiguration": {"OutputLocation": output_location},
    }
    if workgroup:
        params["WorkGroup"] = workgroup

    response = client.start_query_execution(**params)
    query_execution_id = response["QueryExecutionId"]

    logger.info(
        f"{run_id} | PIPELINE_QUERY | SUBMITTED | "
        f"query_execution_id={query_execution_id}"
    )

    deadline = time.time() + timeout_seconds
    while True:
        result = client.get_query_execution(
            QueryExecutionId=query_execution_id
        )
        state = result["QueryExecution"]["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        if time.time() > deadline:
            raise TimeoutError("Athena query timed out")
        time.sleep(2)

    if state != "SUCCEEDED":
        reason = result["QueryExecution"]["Status"].get("StateChangeReason", "")
        raise RuntimeError(
            f"Athena query failed: state={state} reason={reason}"
        )

    logger.info(
        f"{run_id} | PIPELINE_QUERY | OK | "
        f"query_execution_id={query_execution_id}"
    )

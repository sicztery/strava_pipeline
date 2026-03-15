import os
import logging
from google.cloud import bigquery

logger = logging.getLogger("strava_pipeline")


def execute_pipeline_query(run_id: str) -> None:
    """
    Execute the BigQuery pipeline query that transforms raw data into strava_main.
    
    Args:
        run_id: Pipeline run ID for logging
    """
    
    # ======================
    # CONFIG
    # ======================

    PROJECT_ID = os.getenv("STRAVA_GCP_PROJECT")
    DATASET = os.getenv("BQ_DATASET")
    BQ_LOCATION = os.getenv("BQ_LOCATION", "europe-west1")
    
    logger.info(f"{run_id} | BQ_PIPELINE | START | Executing BigQuery pipeline query")
    
    try:
        # Load and execute pipeline query
        bq_client = bigquery.Client(project=PROJECT_ID)
        
        # Get absolute path to SQL file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # app/staging -> app -> strava_pipeline
        base_dir = os.path.dirname(os.path.dirname(script_dir))
        sql_path = os.path.join(base_dir, "sql/pipeline_query.sql")
        
        # Verify SQL file exists
        if not os.path.exists(sql_path):
            raise FileNotFoundError(f"SQL file not found: {sql_path}")
        
        # Read and substitute variables
        with open(sql_path, "r") as f:
            sql_query = f.read()
        
        logger.info(f"{run_id} | BQ_PIPELINE | SQL_LOADED | Query size: {len(sql_query)} bytes")
        
        sql_query = sql_query.replace("${PROJECT_ID}", PROJECT_ID)
        sql_query = sql_query.replace("${DATASET}", DATASET)
        
        # Execute query
        job_config = bigquery.QueryJobConfig(use_legacy_sql=False)
        query_job = bq_client.query(sql_query, job_config=job_config, location=BQ_LOCATION)
        
        logger.info(f"{run_id} | BQ_PIPELINE | JOB_SUBMITTED | Job ID: {query_job.job_id}")
        
        # Wait for query to complete with 5-minute timeout
        query_result = query_job.result(timeout=300)
        
        logger.info(
            f"{run_id} | BQ_PIPELINE | OK | "
            f"BigQuery pipeline executed successfully | "
            f"job_id={query_job.job_id} | rows_affected={query_result.total_rows}"
        )
        
    except FileNotFoundError as e:
        logger.error(f"{run_id} | BQ_PIPELINE | FAIL | SQL file not found: {e}")
        raise
    except Exception as e:
        logger.error(
            f"{run_id} | BQ_PIPELINE | FAIL | Query execution failed: {str(e)}",
            exc_info=True
        )
        raise

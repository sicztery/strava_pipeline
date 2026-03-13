UPDATE `${PROJECT_ID}.${DATASET}.strava_buffer`
SET buffer_ingest_ts = CAST(CURRENT_TIMESTAMP() AS STRING)
WHERE buffer_ingest_ts IS NULL;
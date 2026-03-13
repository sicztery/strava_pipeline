CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.strava_dashboard` AS
SELECT
  activity_id,
  CONCAT(
  '=HYPERLINK("https://www.strava.com/activities/',
  CAST(activity_id AS STRING),
  '";"',
  CAST(activity_id AS STRING),
  '")'
) AS activity_link, 
  CONCAT('https://www.strava.com/activities/', CAST(activity_id AS STRING)) AS activity_url,
  start_date_local,
  DATE(start_date_local)                     AS activity_date,
  EXTRACT(YEAR FROM start_date_local)        AS year,
  EXTRACT(MONTH FROM start_date_local)       AS month,
  distance / 1000                            AS distance_km,
  moving_time / 60                           AS moving_time_min,
  moving_time                                AS moving_time_secs,  
  average_speed                              AS avg_speed_kmh,
  average_heart_rate,
  elevation_gain,
  activity_type,
  DATETIME(ingest_ts, "Europe/Oslo")         AS ingest_ts
FROM `${PROJECT_ID}.${DATASET}.strava_main`
WHERE start_date_local > '2021-01-01' AND
      start_date_local IS NOT NULL
ORDER BY activity_id DESC

-- analytical dashboard-friendly view 
      

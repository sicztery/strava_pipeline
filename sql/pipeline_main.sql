MERGE `${PROJECT_ID}.${DATASET}.strava_main` M
USING (
  SELECT * EXCEPT(rn)
  FROM (
    SELECT
      -- klucz
      SAFE_CAST(activity_id AS INT64)                         AS activity_id,

      -- opis
      name,
      sport_type,

      -- czas
      SAFE.TIMESTAMP(start_date_utc)                          AS start_date_utc,
      SAFE.TIMESTAMP(start_date_local)                        AS start_date_local,
      SAFE_CAST(utc_offset AS INT64)                          AS utc_offset,
      timezone,

      -- metryki ruchu
      SAFE_CAST(distance_m AS FLOAT64)                        AS distance_m,
      SAFE_CAST(moving_time_s AS INT64)                       AS moving_time_s,
      SAFE_CAST(elapsed_time_s AS INT64)                      AS elapsed_time_s,
      SAFE_CAST(elevation_gain_m AS FLOAT64)                  AS elevation_gain_m,

      -- prędkość
      SAFE_CAST(average_speed_kmh AS FLOAT64)                 AS average_speed_kmh,
      SAFE_CAST(max_speed_kmh AS FLOAT64)                     AS max_speed_kmh,

      -- HR
      CAST(SAFE_CAST(average_hr AS FLOAT64) AS INT64)         AS average_hr,
      SAFE_CAST(max_hr AS INT64)                              AS max_hr,
      SAFE_CAST(has_heartrate AS BOOL)                        AS has_heartrate,

      -- cadence / power
      SAFE_CAST(average_cadence AS INT64)                     AS average_cadence,
      SAFE_CAST(average_watts AS INT64)                       AS average_watts,
      max_watts,
      SAFE_CAST(weighted_average_watts AS INT64)              AS weighted_average_watts,
      SAFE_CAST(kilojoules AS INT64)                          AS kilojoules,
      SAFE_CAST(suffer_score AS INT64)                        AS suffer_score,

      -- sprzęt
      device_name,
      gear_id,

      -- geo
      SAFE_CAST(start_lat AS FLOAT64)                          AS start_lat,
      SAFE_CAST(start_lng AS FLOAT64)                          AS start_lng,
      SAFE_CAST(end_lat AS FLOAT64)                            AS end_lat,
      SAFE_CAST(end_lng AS FLOAT64)                            AS end_lng,

      -- flagi
      SAFE_CAST(is_private AS BOOL)                            AS is_private,
      SAFE_CAST(is_commute AS BOOL)                            AS is_commute,
      SAFE_CAST(is_manual AS BOOL)                             AS is_manual,

      -- ingest
      SAFE.TIMESTAMP(buffer_ingest_ts)                         AS ingest_ts,

      -- dedup
      ROW_NUMBER() OVER (
        PARTITION BY SAFE_CAST(activity_id AS INT64)
        ORDER BY SAFE.TIMESTAMP(buffer_ingest_ts) DESC
      ) AS rn

    FROM `${PROJECT_ID}.${DATASET}.strava_buffer`
    WHERE activity_id IS NOT NULL
  )
  WHERE rn = 1
) B
ON M.activity_id = B.activity_id

WHEN NOT MATCHED THEN
  INSERT (
    activity_id,
    activity_name,
    activity_type,
    start_date_utc,
    start_date_local,
    utc_offset,
    timezone,
    distance,
    moving_time,
    elapsed_time,
    elevation_gain,
    average_speed,
    max_speed,
    average_heart_rate,
    max_heart_rate,
    has_heartrate,
    average_cadence,
    average_watts,
    max_watts,
    weighted_average_watts,
    kilojoules,
    suffer_score,
    device_name,
    gear_id,
    start_lat,
    start_lng,
    end_lat,
    end_lng,
    is_private,
    commute,
    is_manual,
    ingest_ts
  )
  VALUES (
    B.activity_id,
    B.name,
    B.sport_type,
    B.start_date_utc,
    B.start_date_local,
    B.utc_offset,
    B.timezone,
    B.distance_m,
    B.moving_time_s,
    B.elapsed_time_s,
    B.elevation_gain_m,
    B.average_speed_kmh,
    B.max_speed_kmh,
    B.average_hr,
    B.max_hr,
    B.has_heartrate,
    B.average_cadence,
    B.average_watts,
    B.max_watts,
    B.weighted_average_watts,
    B.kilojoules,
    B.suffer_score,
    B.device_name,
    B.gear_id,
    B.start_lat,
    B.start_lng,
    B.end_lat,
    B.end_lng,
    B.is_private,
    B.is_commute,
    B.is_manual,
    B.ingest_ts
  );

resource "aws_glue_catalog_database" "athena" {
  count       = var.pipeline_query_engine == "athena" ? 1 : 0
  name        = var.athena_database
  description = "Strava pipeline database"
  tags        = local.tags
}

resource "aws_glue_catalog_table" "strava_raw_ext" {
  count         = var.pipeline_query_engine == "athena" ? 1 : 0
  name          = "strava_raw_ext"
  database_name = aws_glue_catalog_database.athena[0].name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    classification = "json"
  }

  storage_descriptor {
    location      = "s3://${var.bucket_name}/staging/strava/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info {
      serialization_library = "org.openx.data.jsonserde.JsonSerDe"
    }

    columns {
      name = "activity_id"
      type = "string"
    }
    columns {
      name = "name"
      type = "string"
    }
    columns {
      name = "sport_type"
      type = "string"
    }
    columns {
      name = "start_date_utc"
      type = "string"
    }
    columns {
      name = "start_date_local"
      type = "string"
    }
    columns {
      name = "utc_offset"
      type = "string"
    }
    columns {
      name = "timezone"
      type = "string"
    }
    columns {
      name = "distance_m"
      type = "string"
    }
    columns {
      name = "moving_time_s"
      type = "string"
    }
    columns {
      name = "elapsed_time_s"
      type = "string"
    }
    columns {
      name = "elevation_gain_m"
      type = "string"
    }
    columns {
      name = "average_speed_kmh"
      type = "string"
    }
    columns {
      name = "max_speed_kmh"
      type = "string"
    }
    columns {
      name = "average_hr"
      type = "string"
    }
    columns {
      name = "max_hr"
      type = "string"
    }
    columns {
      name = "has_heartrate"
      type = "string"
    }
    columns {
      name = "average_cadence"
      type = "string"
    }
    columns {
      name = "average_watts"
      type = "string"
    }
    columns {
      name = "max_watts"
      type = "string"
    }
    columns {
      name = "weighted_average_watts"
      type = "string"
    }
    columns {
      name = "kilojoules"
      type = "string"
    }
    columns {
      name = "suffer_score"
      type = "string"
    }
    columns {
      name = "device_name"
      type = "string"
    }
    columns {
      name = "gear_id"
      type = "string"
    }
    columns {
      name = "start_lat"
      type = "string"
    }
    columns {
      name = "start_lng"
      type = "string"
    }
    columns {
      name = "end_lat"
      type = "string"
    }
    columns {
      name = "end_lng"
      type = "string"
    }
    columns {
      name = "is_private"
      type = "string"
    }
    columns {
      name = "is_commute"
      type = "string"
    }
    columns {
      name = "is_manual"
      type = "string"
    }
    columns {
      name = "ingest_ts"
      type = "string"
    }
  }
}

resource "aws_glue_catalog_table" "strava_main" {
  count         = var.pipeline_query_engine == "athena" ? 1 : 0
  name          = "strava_main"
  database_name = aws_glue_catalog_database.athena[0].name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    classification = "parquet"
  }

  storage_descriptor {
    location      = "s3://${var.bucket_name}/main/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "activity_id"
      type = "bigint"
    }
    columns {
      name = "activity_name"
      type = "string"
    }
    columns {
      name = "activity_type"
      type = "string"
    }
    columns {
      name = "start_date_utc"
      type = "timestamp"
    }
    columns {
      name = "start_date_local"
      type = "timestamp"
    }
    columns {
      name = "utc_offset"
      type = "double"
    }
    columns {
      name = "timezone"
      type = "string"
    }
    columns {
      name = "distance"
      type = "double"
    }
    columns {
      name = "moving_time"
      type = "bigint"
    }
    columns {
      name = "elapsed_time"
      type = "bigint"
    }
    columns {
      name = "elevation_gain"
      type = "double"
    }
    columns {
      name = "average_speed"
      type = "double"
    }
    columns {
      name = "max_speed"
      type = "double"
    }
    columns {
      name = "average_heart_rate"
      type = "bigint"
    }
    columns {
      name = "max_heart_rate"
      type = "bigint"
    }
    columns {
      name = "has_heartrate"
      type = "boolean"
    }
    columns {
      name = "average_cadence"
      type = "bigint"
    }
    columns {
      name = "average_watts"
      type = "bigint"
    }
    columns {
      name = "max_watts"
      type = "bigint"
    }
    columns {
      name = "weighted_average_watts"
      type = "bigint"
    }
    columns {
      name = "kilojoules"
      type = "bigint"
    }
    columns {
      name = "suffer_score"
      type = "bigint"
    }
    columns {
      name = "device_name"
      type = "string"
    }
    columns {
      name = "gear_id"
      type = "string"
    }
    columns {
      name = "start_lat"
      type = "double"
    }
    columns {
      name = "start_lng"
      type = "double"
    }
    columns {
      name = "end_lat"
      type = "double"
    }
    columns {
      name = "end_lng"
      type = "double"
    }
    columns {
      name = "is_private"
      type = "boolean"
    }
    columns {
      name = "commute"
      type = "boolean"
    }
    columns {
      name = "is_manual"
      type = "boolean"
    }
    columns {
      name = "ingest_ts"
      type = "timestamp"
    }
  }
}

-- Python-Telem online telemetry database setup.
--
-- The app writes one row per emitted telemetry snapshot.
-- It stores the full event in payload JSON and also copies a few top-level
-- values into scalar columns for simple filtering.
--
-- Required environment variables in the Python app:
--   TELEMETRY_STORAGE_MODE=db      -- or "both"
--   TELEMETRY_DB_HOST=...
--   TELEMETRY_DB_PORT=3306         -- optional, defaults to 3306
--   TELEMETRY_DB_USER=...
--   TELEMETRY_DB_PASSWORD=...
--   TELEMETRY_DB_NAME=...
--   TELEMETRY_DB_TABLE=telemetry_events  -- optional
--   TELEMETRY_ONLINE_SEND_INTERVAL_SECONDS=5  -- optional, defaults to 5

CREATE TABLE IF NOT EXISTS telemetry_events (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  received_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  event_time VARCHAR(64) NULL,
  measurement VARCHAR(64) NULL,
  device_tag VARCHAR(64) NULL,
  vehicle_year VARCHAR(32) NULL,
  payload JSON NOT NULL,

  INDEX idx_received_at (received_at),
  INDEX idx_event_time (event_time),
  INDEX idx_device_time (device_tag, received_at),
  INDEX idx_vehicle_time (vehicle_year, received_at)
);

-- The payload stored by the app has this shape:
--
-- {
--   "measurement": "telemetry",
--   "tags": {
--     "device": "device1",
--     "vehicle_year": "2026"
--   },
--   "fields": {
--     "... all vehicle telemetry fields ...": "..."
--   },
--   "timestamp": "2026-06-30T18:42:10.123456"
-- }
--
-- The SQL table above is enough for the current Python app. The app creates
-- this table automatically if it does not exist, but creating it yourself lets
-- you add indexes up front.

-- Optional: generated columns for website reads.
-- Use these when the webpage frequently needs latest location, speed, battery,
-- lap timing, or telemetry health without repeatedly extracting JSON.
--
-- If your database does not support STORED generated columns on JSON, skip this
-- block and use the view further below instead.

ALTER TABLE telemetry_events
  ADD COLUMN nav_lat DECIMAL(10, 7)
    GENERATED ALWAYS AS (
      CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_LAT')) AS DECIMAL(10, 7))
    ) STORED,
  ADD COLUMN nav_lon DECIMAL(10, 7)
    GENERATED ALWAYS AS (
      CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_LON')) AS DECIMAL(10, 7))
    ) STORED,
  ADD COLUMN nav_vehicle_mph DOUBLE
    GENERATED ALWAYS AS (
      CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_VEHICLE_MPH')) AS DOUBLE)
    ) STORED,
  ADD COLUMN nav_gps_valid TINYINT
    GENERATED ALWAYS AS (
      CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_GPS_VALID')) AS UNSIGNED)
    ) STORED,
  ADD COLUMN nav_fix INT
    GENERATED ALWAYS AS (
      CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_FIX')) AS SIGNED)
    ) STORED,
  ADD COLUMN battery_soc_pct DOUBLE
    GENERATED ALWAYS AS (
      CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.BP_ISH_SOC')) AS DOUBLE)
    ) STORED,
  ADD COLUMN battery_pack_power_kw DOUBLE
    GENERATED ALWAYS AS (
      CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.Battery_Pack_Power_kW')) AS DOUBLE)
    ) STORED,
  ADD COLUMN nav_lap_count INT
    GENERATED ALWAYS AS (
      CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_Lap_Count')) AS SIGNED)
    ) STORED,
  ADD COLUMN telemetry_status VARCHAR(32)
    GENERATED ALWAYS AS (
      JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.Telemetry_Status'))
    ) STORED;

CREATE INDEX idx_latest_valid_gps
  ON telemetry_events (nav_gps_valid, received_at);

CREATE INDEX idx_latest_vehicle
  ON telemetry_events (vehicle_year, received_at);

CREATE INDEX idx_lap_count
  ON telemetry_events (nav_lap_count, received_at);

CREATE INDEX idx_telemetry_status
  ON telemetry_events (telemetry_status, received_at);

-- Optional view for webpage/API code.
-- This works even if you do not add generated columns.

CREATE OR REPLACE VIEW telemetry_latest_web_fields AS
SELECT
  id,
  received_at,
  event_time,
  measurement,
  device_tag,
  vehicle_year,
  CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_LAT')) AS DECIMAL(10, 7)) AS nav_lat,
  CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_LON')) AS DECIMAL(10, 7)) AS nav_lon,
  CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_VEHICLE_MPH')) AS DOUBLE) AS nav_vehicle_mph,
  CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_GPS_MPH')) AS DOUBLE) AS nav_gps_mph,
  CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_IMU_MPH')) AS DOUBLE) AS nav_imu_mph,
  CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_GPS_VALID')) AS UNSIGNED) AS nav_gps_valid,
  CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_FIX')) AS SIGNED) AS nav_fix,
  CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_AGE_MS')) AS SIGNED) AS nav_age_ms,
  JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_SOURCE')) AS nav_source,
  CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.BP_ISH_SOC')) AS DOUBLE) AS battery_soc_pct,
  CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.BP_PVS_Voltage')) AS DOUBLE) AS battery_pack_voltage_v,
  CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.BP_ISH_Amps')) AS DOUBLE) AS battery_pack_current_a,
  CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.Battery_Pack_Power_kW')) AS DOUBLE) AS battery_pack_power_kw,
  JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.Battery_Power_Direction')) AS battery_power_direction,
  CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_Lap_Count')) AS SIGNED) AS nav_lap_count,
  JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_Current_Lap_Time')) AS nav_current_lap_time,
  JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_Last_Lap_Time')) AS nav_last_lap_time,
  JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_Best_Lap_Time')) AS nav_best_lap_time,
  JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.NAV_Lap_Status')) AS nav_lap_status,
  JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.Telemetry_Status')) AS telemetry_status,
  JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.Telemetry_Error')) AS telemetry_error,
  CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.Telemetry_Bad_Packet_Count')) AS SIGNED) AS telemetry_bad_packet_count,
  JSON_UNQUOTE(JSON_EXTRACT(payload, '$.fields.Prediction_Quality_Flags')) AS prediction_quality_flags,
  payload
FROM telemetry_events;

-- Latest row for a website backend:
--
-- SELECT *
-- FROM telemetry_latest_web_fields
-- WHERE nav_gps_valid = 1
-- ORDER BY received_at DESC
-- LIMIT 1;

# Telemetry Format

Raw serial telemetry is parsed by `src/data_processor.py`. The parser converts firmware-oriented packet names into canonical output keys from `src/key_name_definitions.py`.

## Common Raw Lines

```text
MC1BUS,0x...,0x...
BME,T=23.65,P=98110.73,H=52.43
NAV,IMU_MPH=0.00,GPS_MPH=0.00,GPS_VALID=0,VEHICLE_MPH=0.00,SOURCE=NONE,LAT=0.000000,LON=0.000000,FIX=0,AGE_MS=4294967295,ELEV_M=214.372,ELEV_VALID=1,ELEV_AGE_MS=84,SATS_VISIBLE=10,SATS_VISIBLE_VALID=1,SATS_VISIBLE_AGE_MS=287,SATS_USED=8,SATS_USED_VALID=1,SATS_USED_AGE_MS=306
IMU_G,VALID=1,CALIBRATED=1,MOUNT_VALID=1,FORWARD_G=0.184,LINEAR_X_G=0.021,LINEAR_Y_G=0.184,LINEAR_Z_G=-0.012,TOTAL_G=1.018,DYNAMIC_G=0.186,PEAK_BOOT_G=0.438,AGE_MS=4
TL_TIM,2026-07-12T12:34:56,UPTIME_MS=123456
TL_UPT,0:00:02:03.456
```

Most packets use this shape:

```text
KEY,HEX_FLOAT_1,HEX_FLOAT_2
```

`HEX_FLOAT_1` and `HEX_FLOAT_2` are decoded as 32-bit floats using the configured endianness. `MC1LIM`, `MC2LIM`, `DC_SWC`, `NAV`, `IMU_G`, `TL_TIM`, and `TL_UPT` have special parsing rules.

## Example Packet Outputs

`MC1BUS,0x...,0x...` produces:

```text
MC1BUS_Voltage
MC1BUS_Current
```

`MC1VEL,0x...,0x...` produces:

```text
MC1VEL_RPM
MC1VEL_Velocity
MC1VEL_Speed
```

`BP_PVS,0x...,0x...` produces:

```text
BP_PVS_Voltage
BP_PVS_milliamp*s
BP_PVS_Ah
```

`BP_ISH` current samples also drive a race-session amp-hour integrator. The
integrator uses the actual monotonic time between samples (normally about one
second), uses trapezoidal integration, and skips gaps longer than five seconds
instead of assuming the last current continued through a telemetry outage. Its
outputs are `Shunt_Used_Ah`, `Shunt_Integration_Status`, and
`Shunt_Sample_Interval_s`; the accumulated value feeds the existing shunt
remaining-capacity fields.

`BME,T=23.65,P=98110.73,H=52.43` produces:

```text
BME_Temperature_C
BME_Pressure_Pa
BME_Humidity_Pct
```

`NAV,...` produces:

```text
NAV_IMU_MPH
NAV_GPS_MPH
NAV_GPS_VALID
NAV_VEHICLE_MPH
NAV_SOURCE
NAV_LAT
NAV_LON
NAV_FIX
NAV_AGE_MS
NAV_ELEV_M
NAV_ELEV_VALID
NAV_ELEV_AGE_MS
NAV_SATS_VISIBLE
NAV_SATS_VISIBLE_VALID
NAV_SATS_VISIBLE_AGE_MS
NAV_SATS_USED
NAV_SATS_USED_VALID
NAV_SATS_USED_AGE_MS
```

`IMU_G,...` produces:

```text
IMU_G_VALID
IMU_G_CALIBRATED
IMU_G_MOUNT_VALID
IMU_FORWARD_G
IMU_LINEAR_X_G
IMU_LINEAR_Y_G
IMU_LINEAR_Z_G
IMU_TOTAL_G
IMU_DYNAMIC_G
IMU_PEAK_BOOT_G
IMU_G_AGE_MS
```

Use elevation only when `NAV_ELEV_VALID=1`. Use processed acceleration only
when both `IMU_G_VALID=1` and `IMU_G_CALIBRATED=1`. `IMU_FORWARD_G` is signed
(positive acceleration, negative braking), `IMU_TOTAL_G` includes gravity,
and `IMU_DYNAMIC_G` has the calibrated gravity vector removed.

The GPS map tab may add route fields after a GPX route is loaded:

```text
NAV_Route_Name
NAV_Checkpoint_Name
NAV_Route_Distance_Remaining
NAV_Checkpoint_Distance_Remaining
NAV_Checkpoint_ETA
```

The GPS map tab may also add lap timing fields after a start/end line is set:

```text
NAV_Lap_Count
NAV_Current_Lap_Time
NAV_Last_Lap_Time
NAV_Best_Lap_Time
NAV_Lap_Status
```

`TL_TIM,12:34:56` produces an uptime-style device timestamp:

```text
device_timestamp = 12:34:56 uptime
```

If firmware sends an ISO datetime instead, the app displays it as local time
plus UTC so the timezone is explicit.

New firmware may append the board's millisecond uptime counter and send a
separate human-readable uptime line:

```text
TL_TIM,2026-07-12T12:34:56,UPTIME_MS=123456
TL_UPT,0:00:02:03.456
```

These produce `device_timestamp`, `board_uptime_ms`, and `board_uptime`.
The older `TL_TIM,12:34:56` form remains supported.

Placeholder or bad telemetry packets such as `0xHHHHHHHH` are converted into
telemetry health fields instead of silently becoming normal numeric data:

```text
Telemetry_Status
Telemetry_Error
Telemetry_Bad_Packet_Count
Telemetry_Last_Bad_Raw
```

## Canonical Keys

Use `TelemetryKey` in `src/key_name_definitions.py` instead of hard-coded strings when adding GUI fields, CSV columns, or parser outputs. `KEY_UNITS` is generated from the same enum and should be treated as the canonical units map.

## CSV Unit Metadata

Primary telemetry CSV rows include `csv_units_mode` and `csv_units_note`.
Numeric telemetry values are converted to the selected application unit mode
when the row is written where a conversion is defined. Because the unit mode can
be changed while the app is running, read `csv_units_mode` per row instead of
assuming the entire file stayed metric or imperial.

## Prediction Fields

After the buffer has a complete enough live snapshot, the app adds local
machine-learning predictions:

```text
Predicted_Remaining_Time
Predicted_Exact_Time
Predicted_BreakEven_Speed
Predicted_Remaining_Time_Uncertainty
Predicted_BreakEven_Speed_Uncertainty
Prediction_Data_Age_s
Prediction_Quality_Flags
```

These fields are derived from `training_data.csv` and the models in
`src/learning_datasets/`. They are not raw serial packets. See
`docs/MACHINE_LEARNING.md` for the feature columns, target columns, retraining
workflow, and interpretation of quality flags.

## Solcast Weather Fields

When Solcast is configured, the app writes live weather fields and forecast
horizons into the normal telemetry stream and CSV. Forecasts are captured at
30 minutes, 1 hour, and 24 hours ahead using these prefixes:

```text
Solcast_Fcst_30m_*
Solcast_Fcst_1h_*
Solcast_Fcst_24h_*
```

The legacy `Solcast_Fcst_*` fields mirror the 30-minute forecast. Each Solcast
prefix may include `GHI`, `DNI`, `DHI`, `GTI`, `Temp`, `Time`, `Fetched_At`,
`Weather_Type`, `CAPE`, `Cloud_Opacity`, `Relative_Humidity`,
`Dewpoint_Temp`, `Wind_Direction_10m`, `Wind_Speed_10m`, `Wind_Gust`,
`Precipitable_Water`, `Precipitation_Rate`, `Surface_Pressure`,
`Clearsky_GHI`, `Clearsky_DNI`, `Zenith`, and `Azimuth`.

Solcast is polled every five minutes. In **Settings > API & Solar**, enable
**Follow valid vehicle GPS every 5 minutes** to use the newest valid telemetry
position for each poll. The manually configured latitude and longitude remain
the fallback until GPS is valid, or whenever GPS following is disabled.

## Adding a New Packet

1. Add canonical output fields to `TelemetryKey`.
2. Add parser logic in `DataProcessor.parse_data()`.
3. Add CSV/UI fields only where the value needs to be displayed or persisted.
4. Update this document with one raw example and its output keys.

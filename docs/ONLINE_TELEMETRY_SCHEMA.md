# Online Telemetry Schema

This is the webpage/API-facing shape of telemetry emitted by the Python telemetry app.

The app sends one combined vehicle snapshot after each buffer flush. Simulation data is not sent online.

Local CSV still records every flushed snapshot. Online HTTP/database ingest is throttled by
`TELEMETRY_ONLINE_SEND_INTERVAL_SECONDS`, which defaults to `5` seconds.

## Storage Paths

The app supports three storage modes:

| Mode | Behavior |
| --- | --- |
| `http` | POST JSON to the configured ingest URL. |
| `db` | Insert JSON directly into the configured MariaDB/MySQL table. |
| `both` | Do both. |

## Direct Database Table

When direct database storage is enabled, the app writes to `telemetry_events` by default.

```sql
CREATE TABLE IF NOT EXISTS telemetry_events (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  received_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  event_time VARCHAR(64) NULL,
  measurement VARCHAR(64) NULL,
  device_tag VARCHAR(64) NULL,
  vehicle_year VARCHAR(32) NULL,
  driver_name VARCHAR(128) NULL,
  payload JSON NOT NULL
);
```

The scalar columns are copied from the JSON for easy filtering:

| Column | Source |
| --- | --- |
| `event_time` | `payload.timestamp` |
| `measurement` | `payload.measurement` |
| `device_tag` | `payload.tags.device` |
| `vehicle_year` | `payload.tags.vehicle_year` |
| `driver_name` | `payload.tags.driver` |
| `payload` | Full telemetry JSON event |

## Legacy/Database Payload

This is the payload stored in the direct database path, and it is also the default HTTP payload format.

```json
{
  "measurement": "telemetry",
  "tags": {
    "device": "device1",
    "vehicle_year": "2026",
    "driver": "Driver Name"
  },
  "fields": {
    "Driver": "Driver Name",
    "NAV_LAT": 42.291707,
    "NAV_LON": -85.587229,
    "NAV_VEHICLE_MPH": 35.2,
    "NAV_GPS_VALID": 1,
    "Telemetry_Status": "OK"
  },
  "timestamp": "2026-06-30T18:42:10.123456"
}
```

## HTTP Payload Formats

The Settings tab can choose one of these payload formats.

### `legacy`

Same as the database payload:

```json
{
  "measurement": "telemetry",
  "tags": {
    "device": "device1",
    "vehicle_year": "2026",
    "driver": "Driver Name"
  },
  "fields": {
    "Driver": "Driver Name"
  },
  "timestamp": "2026-06-30T18:42:10.123456"
}
```

### `ionos`

```json
{
  "session_id": "live-session",
  "vehicle": "2026",
  "data": {},
  "timestamp": "2026-06-30T18:42:10.123456"
}
```

### `dual`

Includes both shapes for compatibility:

```json
{
  "measurement": "telemetry",
  "tags": {
    "device": "device1",
    "vehicle_year": "2026",
    "driver": "Driver Name"
  },
  "fields": {
    "Driver": "Driver Name"
  },
  "timestamp": "2026-06-30T18:42:10.123456",
  "session_id": "live-session",
  "vehicle": "2026",
  "data": {}
}
```

In `legacy`/database mode, webpage code should read vehicle data from `payload.fields`.
In `ionos` mode, webpage code should read vehicle data from `payload.data`.
In `dual` mode, both are available.

## Recommended Webpage DTO

For most webpages, expose a smaller public read endpoint such as `GET /api/telemetry/latest`:

```json
{
  "timestamp": "2026-06-30T18:42:10.123456",
  "device": "device1",
  "vehicle_year": "2026",
  "driver": "Driver Name",
  "position": {
    "lat": 42.291707,
    "lon": -85.587229,
    "gps_valid": true,
    "fix": 3,
    "age_ms": 120
  },
  "speed": {
    "vehicle_mph": 35.2,
    "gps_mph": 35.0,
    "imu_mph": 35.4,
    "source": "GPS"
  },
  "battery": {
    "soc_pct": 82.1,
    "pack_voltage_v": 104.3,
    "pack_current_a": 12.4,
    "pack_power_kw": 1.29,
    "direction": "Discharging"
  },
  "race": {
    "lap_count": 4,
    "current_lap_time": "00:01:22",
    "last_lap_time": "00:02:10",
    "best_lap_time": "00:02:05",
    "lap_status": "Timing"
  },
  "telemetry": {
    "status": "OK",
    "error": "",
    "bad_packet_count": 0
  }
}
```

## Field Dictionary

Values can be numeric, string, empty string, `N/A`, or `null` after JSON sanitizing. Webpages should handle missing fields gracefully because each live snapshot is assembled from many incoming telemetry packets.

### Time And Telemetry Health

| Field | Unit | Meaning |
| --- | --- | --- |
| `timestamp` | local datetime string | App-side timestamp in the combined telemetry fields. |
| `device_timestamp` | uptime / local time | `TL_TIM` value reported by the telemetry device. Uptime-only values display as `hh:mm:ss uptime`; ISO datetime values display as local time plus UTC. |
| `board_uptime` | `d:hh:mm:ss.sss` | Human-readable board uptime reported by `TL_UPT` or derived from `TL_TIM`'s `UPTIME_MS`. |
| `board_uptime_ms` | ms | Raw board uptime counter appended to `TL_TIM` by newer firmware. |
| `Telemetry_Status` | status | `OK` or `BAD_PACKET`. |
| `Telemetry_Error` | text | Last bad telemetry reason in the current flush interval. |
| `Telemetry_Bad_Packet_Count` | count | Cumulative bad packet count from the parser. |
| `Telemetry_Last_Bad_Raw` | text | Last raw bad packet line. |
| `Driver` | text | Manually entered driver name from the desktop Settings tab. |

### Motor Controller 1

| Field | Unit |
| --- | --- |
| `MC1BUS_Voltage` | V |
| `MC1BUS_Current` | A |
| `MC1VEL_RPM` | RPM |
| `MC1VEL_Velocity` | M/s |
| `MC1VEL_Speed` | Mph |
| `MC1TP1_Heatsink_Temp` | °C |
| `MC1TP1_Motor_Temp` | °C |
| `MC1TP2_Inlet_Temp` | °C |
| `MC1TP2_CPU_Temp` | °C |
| `MC1PHA_Phase_A_Current` | A |
| `MC1PHA_Phase_B_current` | A |
| `MC1CUM_Bus_Amphours` | Ah |
| `MC1CUM_Odometer` | m |
| `MC1VVC_VD_Vector` | V |
| `MC1VVC_VQ_Vector` | V |
| `MC1IVC_ID_Vector` | A |
| `MC1IVC_IQ_Vector` | A |
| `MC1BEM_BEMFD_Vector` | V |
| `MC1BEM_BEMFQ_Vector` | V |
| `MC1_Bus_Power_W` | W |
| `MC1_Mechanical_Power_W` | W |
| `MC1_Efficiency_Pct` | % |

### Motor Controller 2

| Field | Unit |
| --- | --- |
| `MC2BUS_Voltage` | V |
| `MC2BUS_Current` | A |
| `MC2VEL_RPM` | RPM |
| `MC2VEL_Velocity` | M/s |
| `MC2VEL_Speed` | Mph |
| `MC2TP1_Heatsink_Temp` | °C |
| `MC2TP1_Motor_Temp` | °C |
| `MC2TP2_Inlet_Temp` | °C |
| `MC2TP2_CPU_Temp` | °C |
| `MC2PHA_Phase_A_Current` | A |
| `MC2PHA_Phase_B_Current` | A |
| `MC2CUM_Bus_Amphours` | Ah |
| `MC2CUM_Odometer` | m |
| `MC2VVC_VD_Vector` | V |
| `MC2VVC_VQ_Vector` | V |
| `MC2IVC_ID_Vector` | A |
| `MC2IVC_IQ_Vector` | A |
| `MC2BEM_BEMFD_Vector` | V |
| `MC2BEM_BEMFQ_Vector` | V |
| `MC2_Bus_Power_W` | W |
| `MC2_Mechanical_Power_W` | W |
| `MC2_Efficiency_Pct` | % |

### Motor Totals

| Field | Unit |
| --- | --- |
| `Motors_Total_Bus_Power_W` | W |
| `Motors_Total_Mechanical_Power_W` | W |
| `Motors_Average_Efficiency_Pct` | % |

### Driver Controls

| Field | Unit |
| --- | --- |
| `DC_DRV_Motor_Velocity_Setpoint` | raw |
| `DC_DRV_Motor_Current_Setpoint` | % |
| `DC_SWC_Position` | text/raw |
| `DC_SWC_Value` | bit string/raw |

### Battery Pack Raw Values

| Field | Unit |
| --- | --- |
| `BP_VMX_ID` | # |
| `BP_VMX_Voltage` | V |
| `BP_VMN_ID` | # |
| `BP_VMN_Voltage` | V |
| `BP_TMX_ID` | # |
| `BP_TMX_Temperature` | °F |
| `BP_ISH_SOC` | % |
| `BP_ISH_Amps` | A |
| `BP_PVS_Voltage` | V |
| `BP_PVS_milliamp*s` | mA*s |
| `BP_PVS_Ah` | Ah |

### Battery Calculated Values

| Field | Unit |
| --- | --- |
| `Battery_String_Imbalance_V` | V |
| `Battery_String_Imbalance_Pct` | % |
| `Battery_Pack_Power_W` | W |
| `Battery_Pack_Power_kW` | kW |
| `Battery_Power_Direction` | `Charging`, `Discharging`, or `Idle` |
| `Battery_C_Rate` | C |
| `Total_Capacity_Wh` | Wh |
| `Total_Capacity_Ah` | Ah |
| `Total_Voltage` | V |

### Remaining Capacity And Prediction

| Field | Unit |
| --- | --- |
| `Shunt_Remaining_Ah` | Ah |
| `Used_Ah_Remaining_Ah` | Ah |
| `Shunt_Remaining_wh` | Wh |
| `Used_Ah_Remaining_wh` | Wh |
| `Shunt_Remaining_Time` | hours |
| `Used_Ah_Remaining_Time` | hours |
| `Used_Ah_Exact_Time` | `hh:mm:ss` |
| `Predicted_Remaining_Time` | hours or status text |
| `Predicted_Remaining_Time_Uncertainty` | hours |
| `Predicted_Exact_Time` | `hh:mm:ss` |
| `Predicted_BreakEven_Speed` | mph or status text |
| `Predicted_BreakEven_Speed_Uncertainty` | mph |
| `Prediction_Data_Age_s` | seconds |
| `Prediction_Quality_Flags` | text |

### Motor Controller Limits

| Field | Unit |
| --- | --- |
| `MC1LIM_CAN_Receive_Error_Count` | count |
| `MC1LIM_CAN_Transmit_Error_Count` | count |
| `MC1LIM_Active_Motor_Info` | raw integer |
| `MC1LIM_Errors` | text list |
| `MC1LIM_Limits` | text list |
| `MC2LIM_CAN_Receive_Error_Count` | count |
| `MC2LIM_CAN_Transmit_Error_Count` | count |
| `MC2LIM_Active_Motor_Info` | raw integer |
| `MC2LIM_Errors` | text list |
| `MC2LIM_Limits` | text list |

### Ambient Sensor

| Field | Unit |
| --- | --- |
| `BME_Temperature_C` | °C |
| `BME_Pressure_Pa` | Pa |
| `BME_Humidity_Pct` | % |

### Solar / Solcast

| Field | Unit |
| --- | --- |
| `Solcast_Live_GHI` | W/m² |
| `Solcast_Live_DNI` | W/m² |
| `Solcast_Live_Temp` | °C |
| `Solcast_Live_Time` | local / UTC |
| `Solcast_Live_Fetched_At` | local / UTC |
| `Solcast_Live_Weather_Type` | text |
| `Solcast_Live_CAPE` | J/kg |
| `Solcast_Live_Cloud_Opacity` | % |
| `Solcast_Live_Relative_Humidity` | % |
| `Solcast_Live_Wind_Direction_10m` | deg |
| `Solcast_Live_Precipitable_Water` | kg/m² |
| `Solcast_Live_Precipitation_Rate` | mm/h |

Forecast fields are emitted for `Solcast_Fcst_30m_*`, `Solcast_Fcst_1h_*`, and
`Solcast_Fcst_24h_*`. The legacy `Solcast_Fcst_*` fields mirror the 30-minute
forecast for compatibility.

| Field Suffix | Unit |
| --- | --- |
| `Time` | local / UTC |
| `Fetched_At` | local / UTC |
| `GHI` | W/m² |
| `DNI` | W/m² |
| `Temp` | °C |
| `Weather_Type` | text |
| `CAPE` | J/kg |
| `Cloud_Opacity` | % |
| `Relative_Humidity` | % |
| `DHI` | W/m² |
| `GTI` | W/m² |
| `Dewpoint_Temp` | °C |
| `Wind_Direction_10m` | deg |
| `Wind_Speed_10m` | m/s |
| `Wind_Gust` | m/s |
| `Precipitable_Water` | kg/m² |
| `Precipitation_Rate` | mm/h |
| `Surface_Pressure` | hPa |
| `Clearsky_GHI` | W/m² |
| `Clearsky_DNI` | W/m² |
| `Zenith` | deg |
| `Azimuth` | deg |

When valid GPS telemetry is available, the desktop app can move the Solcast
query point during a race. It checks once per flushed telemetry snapshot, but
only updates Solcast coordinates after at least 1 hour and 15-30 miles of
movement from the previous Solcast query point. A persisted daily cap of 10
automatic location updates prevents restarts from accidentally exceeding the
race-day location budget.

### GPS, Route, And Lap Timing

| Field | Unit | Meaning |
| --- | --- | --- |
| `NAV_IMU_MPH` | mph | IMU-derived speed. |
| `NAV_GPS_MPH` | mph | GPS-derived speed. |
| `NAV_GPS_VALID` | boolean-ish integer | `1` means valid. |
| `NAV_VEHICLE_MPH` | mph | Selected vehicle speed. |
| `NAV_SOURCE` | text | Speed/location source. |
| `NAV_LAT` | degrees | Latitude. |
| `NAV_LON` | degrees | Longitude. |
| `NAV_FIX` | integer | GPS fix type/status. |
| `NAV_AGE_MS` | ms | Age of GPS data. |
| `NAV_Route_Name` | text | Loaded route name(s). |
| `NAV_Checkpoint_Name` | text | Current/next checkpoint segment. |
| `NAV_Route_Distance_Remaining` | mi | Remaining route distance. |
| `NAV_Checkpoint_Distance_Remaining` | mi | Remaining distance to checkpoint. |
| `NAV_Checkpoint_ETA` | `hh:mm:ss` | ETA to checkpoint. |
| `NAV_Lap_Count` | laps | Completed lap count. |
| `NAV_Current_Lap_Time` | `hh:mm:ss` | Current lap timer. |
| `NAV_Last_Lap_Time` | `hh:mm:ss` | Last completed lap. |
| `NAV_Best_Lap_Time` | `hh:mm:ss` | Best completed lap. |
| `NAV_Lap_Status` | text | Lap timing status. |

## Best Fields For A Website Dashboard

For a public live page, start with:

| UI Area | Fields |
| --- | --- |
| Map | `NAV_LAT`, `NAV_LON`, `NAV_GPS_VALID`, `NAV_FIX`, `NAV_AGE_MS` |
| Speed | `NAV_VEHICLE_MPH`, `NAV_GPS_MPH`, `NAV_IMU_MPH`, `NAV_SOURCE` |
| Battery | `BP_ISH_SOC`, `BP_PVS_Voltage`, `BP_ISH_Amps`, `Battery_Pack_Power_kW`, `Battery_Power_Direction` |
| Race | `NAV_Lap_Count`, `NAV_Current_Lap_Time`, `NAV_Last_Lap_Time`, `NAV_Best_Lap_Time`, `NAV_Lap_Status` |
| Health | `Telemetry_Status`, `Telemetry_Error`, `MC1LIM_Errors`, `MC2LIM_Errors`, `Prediction_Quality_Flags` |
| Solar | `Solcast_Live_GHI`, `Solcast_Fcst_GHI`, `Solcast_Live_Temp`, `Solcast_Fcst_Temp` |

## Notes For Backend/Webpage Code

- Do not expose the ingest API key in browser JavaScript.
- Browser pages should call a public read endpoint, not the protected ingest endpoint.
- Treat `NAV_GPS_VALID != 1` as "do not update map marker" or show stale/invalid state.
- Treat `Telemetry_Status != "OK"` as a data quality warning.
- Non-finite numbers are sanitized before HTTP send; expect `null` for impossible numeric values.
- Some fields may be `N/A` until the corresponding subsystem has reported at least once.

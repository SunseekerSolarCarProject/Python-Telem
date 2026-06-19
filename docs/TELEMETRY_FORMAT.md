# Telemetry Format

Raw serial telemetry is parsed by `src/data_processor.py`. The parser converts firmware-oriented packet names into canonical output keys from `src/key_name_definitions.py`.

## Common Raw Lines

```text
MC1BUS,0x...,0x...
BME,T=23.65,P=98110.73,H=52.43
NAV,IMU_MPH=0.00,GPS_MPH=0.00,GPS_VALID=0,VEHICLE_MPH=0.00,SOURCE=NONE,LAT=0.000000,LON=0.000000,FIX=0,AGE_MS=4294967295
TL_TIM,12:34:56
```

Most packets use this shape:

```text
KEY,HEX_FLOAT_1,HEX_FLOAT_2
```

`HEX_FLOAT_1` and `HEX_FLOAT_2` are decoded as 32-bit floats using the configured endianness. `MC1LIM`, `MC2LIM`, `DC_SWC`, `NAV`, and `TL_TIM` have special parsing rules.

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
```

The GPS map tab may add route fields after a GPX route is loaded:

```text
NAV_Route_Name
NAV_Checkpoint_Name
NAV_Route_Distance_Remaining
NAV_Checkpoint_Distance_Remaining
NAV_Checkpoint_ETA
```

`TL_TIM,12:34:56` produces:

```text
device_timestamp
```

## Canonical Keys

Use `TelemetryKey` in `src/key_name_definitions.py` instead of hard-coded strings when adding GUI fields, CSV columns, or parser outputs. `KEY_UNITS` is generated from the same enum and should be treated as the canonical units map.

## Adding a New Packet

1. Add canonical output fields to `TelemetryKey`.
2. Add parser logic in `DataProcessor.parse_data()`.
3. Add CSV/UI fields only where the value needs to be displayed or persisted.
4. Update this document with one raw example and its output keys.

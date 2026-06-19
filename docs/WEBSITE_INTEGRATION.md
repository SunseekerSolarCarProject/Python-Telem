# Website Integration

The telemetry app sends vehicle data to a website through an HTTP API endpoint. It does not upload a `.json` file.

## Required Backend

A static browser page cannot securely receive telemetry directly. The website needs a backend API endpoint or serverless function that can:

1. Receive a `POST` request from the Python app.
2. Validate the API key.
3. Parse the telemetry JSON.
4. Store the latest position and speed.
5. Return a JSON response.

The browser can then fetch already-stored telemetry from a public read endpoint.

## Recommended Flow

```text
Telemetry app
  POSTs JSON telemetry with an API key

Backend/API endpoint
  validates and stores the latest telemetry

Website JavaScript
  GETs the latest stored telemetry and updates the map
```

## Recommended Endpoints

```text
POST /api/telemetry/ingest
GET  /api/telemetry/latest
```

The secret ingest API key should only exist in the Python telemetry app and on the backend. Do not put it in browser JavaScript.

## Auth Headers

The telemetry app can send the configured key as:

```text
Authorization: Bearer YOUR_API_KEY
X-API-KEY: YOUR_API_KEY
X-API-Token: YOUR_API_KEY
```

The `auto` auth mode sends all common headers for compatibility.

## Legacy Payload

```json
{
  "measurement": "telemetry",
  "tags": {
    "device": "device1",
    "vehicle_year": "2026"
  },
  "fields": {
    "NAV_LAT": 42.291707,
    "NAV_LON": -85.587229,
    "NAV_VEHICLE_MPH": 35.2,
    "NAV_GPS_VALID": 1,
    "NAV_FIX": 3,
    "NAV_SOURCE": "GPS",
    "NAV_AGE_MS": 120
  },
  "timestamp": "2026-06-18T12:34:56.000000"
}
```

Fields usually needed for live vehicle tracking:

```text
fields.NAV_LAT
fields.NAV_LON
fields.NAV_VEHICLE_MPH
fields.NAV_GPS_VALID
fields.NAV_FIX
timestamp
```

## Response Contract

When "Require JSON response" is enabled, the ingest endpoint should return:

```text
HTTP 200
Content-Type: application/json
```

```json
{ "ok": true }
```

If the app receives HTML, the configured URL probably points to the website frontend rather than the backend ingest endpoint.

## Backend Sketch

```text
token = request.headers["x-api-key"]

if token != EXPECTED_API_KEY:
    return 401, { "ok": false, "error": "unauthorized" }

fields = request.json["fields"]

latest = {
    "lat": fields["NAV_LAT"],
    "lon": fields["NAV_LON"],
    "speed_mph": fields["NAV_VEHICLE_MPH"],
    "gps_valid": fields["NAV_GPS_VALID"],
    "fix": fields["NAV_FIX"],
    "timestamp": request.json["timestamp"]
}

save_latest_telemetry(latest)

return 200, { "ok": true }
```

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

For the full field dictionary and webpage-facing payload shapes, see
`docs/ONLINE_TELEMETRY_SCHEMA.md`.

## Database Options

There are two valid ways to gather and store telemetry data. This website is
currently using Option 1.

### Option 1: IONOS Website Database

Use this when the telemetry app should send data to `cagedmotion.com` and let
the website's hosted backend store it.

```text
Telemetry app
  -> HTTPS POST to cagedmotion.com ingest API
  -> IONOS Python CGI backend
  -> IONOS MariaDB telemetry_events table
  -> Website/phone app reads public latest endpoint
```

This is the recommended setup for the current site because IONOS allows code
running on the hosted webspace to talk to the IONOS MariaDB database. It also
keeps database credentials off laptops, browsers, and phone apps.

Use these production URLs:

```text
POST https://cagedmotion.com/ingest-api/run_wsgi.py/telemetry
GET  https://cagedmotion.com/ingest-api/run_wsgi.py/api/telemetry/latest
```

Database credentials live only in:

```text
~/htdocs/ingest-api/.env
```

The telemetry app only needs the ingest URL and `API_AUTH_TOKEN`. Browser pages
and phone apps only need the public latest read URL.

### Option 2: Self-Managed Database/API

Use this when you want telemetry data stored somewhere other than IONOS, such
as a VPS, Raspberry Pi server, cloud VM, Supabase, Railway, Fly.io, AWS, or a
team-owned backend.

```text
Telemetry app
  -> HTTPS POST to your own ingest API
  -> Your backend
  -> Your database
  -> Website/phone app reads your public read endpoint
```

In this option, the endpoint paths can stay conceptually the same:

```text
POST https://your-api.example.com/api/telemetry/ingest
GET  https://your-api.example.com/api/telemetry/latest
```

Your backend should still follow the same contract:

- Validate the ingest API token.
- Accept the `legacy` or `dual` telemetry payload.
- Store the event in a table like `telemetry_events`.
- Expose a public read endpoint that returns the webpage DTO.
- Keep database credentials and ingest tokens out of browser JavaScript.

This option is better if you need higher ingest rates, long-term history,
background workers, analytics, websockets, or more control than IONOS shared
hosting gives you.

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
POST /ingest-api/run_wsgi.py/telemetry
GET  /ingest-api/run_wsgi.py/api/telemetry/latest
```

IONOS runs the backend through Python CGI, so `run_wsgi.py` is part of the
production URL. Do not point the telemetry app at the website root or a React
page route.

Telemetry app settings:

```text
Storage mode: http
Ingest URL: https://cagedmotion.com/ingest-api/run_wsgi.py/telemetry
Payload format: legacy or dual
Auth mode: auto or X-API-Token
API token: same value as API_AUTH_TOKEN in ingest-api/.env on the server
Require JSON response: enabled
```

The API also accepts `/api/telemetry/ingest` and `/ingest` as aliases when
called through the same CGI base path, but `/telemetry` is the recommended
production route.

The secret ingest API key should only exist in the Python telemetry app and on the backend. Do not put it in browser JavaScript.

## Auth Headers

The telemetry app can send the configured key as:

```text
Authorization: Bearer YOUR_API_KEY
X-API-KEY: YOUR_API_KEY
X-API-Token: YOUR_API_KEY
```

The `auto` auth mode sends all common headers for compatibility.

On IONOS, `Authorization` may not always be forwarded to CGI scripts, so
`X-API-Token` is the safest single header. The telemetry app's `auto` auth mode
is preferred because it sends the compatibility headers together.

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
    "NAV_AGE_MS": 120,
    "NAV_ELEV_M": 214.372,
    "NAV_ELEV_VALID": 1,
    "NAV_ELEV_AGE_MS": 84,
    "IMU_G_VALID": 1,
    "IMU_G_CALIBRATED": 1,
    "IMU_FORWARD_G": 0.184,
    "IMU_DYNAMIC_G": 0.186,
    "IMU_PEAK_BOOT_G": 0.438
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
fields.NAV_ELEV_M
fields.NAV_ELEV_VALID
fields.IMU_FORWARD_G
fields.IMU_DYNAMIC_G
fields.IMU_PEAK_BOOT_G
timestamp
```

## Response Contract

When "Require JSON response" is enabled, the ingest endpoint should return:

```text
HTTP 200
Content-Type: application/json
```

```json
{ "ok": true, "status": "ok", "event_id": 123 }
```

If the app receives HTML, the configured URL probably points to the website frontend rather than the backend ingest endpoint.

## Database Storage

The website API stores telemetry app uploads in the `telemetry_events` table:

```sql
CREATE TABLE IF NOT EXISTS telemetry_events (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  received_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  event_time VARCHAR(64) NULL,
  measurement VARCHAR(64) NULL,
  device_tag VARCHAR(64) NULL,
  vehicle_year VARCHAR(32) NULL,
  payload JSON NOT NULL
);
```

The full telemetry JSON is saved in `payload`. The scalar columns are copied
from `payload.timestamp`, `payload.measurement`, `payload.tags.device`, and
`payload.tags.vehicle_year` for easier filtering.

The browser should read from the public latest endpoint:

```text
GET https://cagedmotion.com/ingest-api/run_wsgi.py/api/telemetry/latest
```

That endpoint returns a smaller webpage-friendly object with `position`,
`speed`, `battery`, `race`, and `telemetry` sections.

## Reading Telemetry Data

The ingest endpoint is protected, but the latest read endpoint is public:

```text
GET https://cagedmotion.com/ingest-api/run_wsgi.py/api/telemetry/latest
```

Use this endpoint for:

- Pages on `cagedmotion.com`
- Other websites/domains that need to display the car position
- Mobile/phone applications
- Small dashboards or map displays

No API token is required for reads. Only upload/ingest requests use
`API_AUTH_TOKEN`.

### Latest Response Shape

```json
{
  "ok": true,
  "latest": {
    "timestamp": "2026-06-30T16:33:22.042172",
    "received_at": "2026-06-30T16:33:22.000",
    "device": "device1",
    "vehicle_year": "2026",
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
      "error": null,
      "bad_packet_count": 0
    }
  }
}
```

### Browser/React Example

```js
async function fetchLatestTelemetry() {
  const response = await fetch(
    'https://cagedmotion.com/ingest-api/run_wsgi.py/api/telemetry/latest'
  );

  if (!response.ok) {
    throw new Error(`Telemetry read failed: ${response.status}`);
  }

  const body = await response.json();
  return body.ok ? body.latest : null;
}

const latest = await fetchLatestTelemetry();
const lat = latest?.position?.lat;
const lon = latest?.position?.lon;

if (latest?.position?.gps_valid && Number.isFinite(lat) && Number.isFinite(lon)) {
  updateMapMarker({
    lat,
    lon,
    speedMph: latest.speed.vehicle_mph,
  });
}
```

### Other Domains

Other domains can call the same public read endpoint with normal HTTPS `GET`
requests. If a browser on another domain is blocked by CORS, add that domain to
`ALLOWED_ORIGINS` in `~/htdocs/ingest-api/.env`, or use `ALLOWED_ORIGINS=*` for
a public read dashboard.

Example:

```env
ALLOWED_ORIGINS=https://cagedmotion.com,https://dashboard.example.com
```

After changing `.env`, the next CGI request loads the new value.

### Phone App Example

Phone apps can poll the public read endpoint without the ingest token:

```text
GET https://cagedmotion.com/ingest-api/run_wsgi.py/api/telemetry/latest
Accept: application/json
```

Recommended polling interval:

```text
Map/live UI: every 5-10 seconds
Background refresh: every 15-30 seconds
```

Avoid polling every second from many devices. The site runs on IONOS shared
hosting, and the endpoint is a Python CGI request.

### Map Coordinate Rules

Only update the map marker when all of these are true:

```text
latest.position.gps_valid === true
latest.position.lat is not null
latest.position.lon is not null
```

Recommended stale-data handling:

```js
const receivedAt = new Date(latest.received_at || latest.timestamp);
const ageMs = Date.now() - receivedAt.getTime();
const stale = ageMs > 30000;
```

If data is stale:

- Keep the last marker position but show a stale/offline state.
- Do not jump the marker to `null`, `0,0`, or invalid coordinates.
- Show `latest.telemetry.error` when `latest.telemetry.status !== 'OK'`.

### Future Read Endpoints

The current read endpoint returns only the latest DTO. Add separate public
endpoints later if the website or phone app needs:

- Last 50 map points
- Battery history
- Race/lap history
- Vehicle-specific reads such as `/api/telemetry/latest?vehicle_year=2026`

## Smoke Test

After deployment, test the same path used by the telemetry app:

```bash
cd ~/htdocs/ingest-api
python3 event_smoke_test.py \
  --url https://cagedmotion.com/ingest-api/run_wsgi.py \
  --token '<API_AUTH_TOKEN>'
```

Success looks like a JSON response containing both `posted` and `latest`.

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

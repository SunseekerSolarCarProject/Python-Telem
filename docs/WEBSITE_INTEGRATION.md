# Website Integration

The telemetry app includes an option intended to supply live vehicle data for
`sunseekerwmu.org` through the team's own database. This integration is planned
for the near future; it is not currently configured or in production.

An earlier interim solution sent telemetry through an HTTP API hosted at
`cagedmotion.com`. References to that domain in this document describe the
former solution and should not be interpreted as the current production
configuration for `sunseekerwmu.org`.

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

There are two supported ways to gather and store telemetry data. The
Sunseeker-owned database path is the planned near-future method for showing live
information on `sunseekerwmu.org`; it still requires deployment and
configuration.

### Option 1: Sunseeker-Owned Database (Planned)

Use direct database storage when the planned Sunseeker website integration is
deployed.

```text
Telemetry app
  -> Team-owned telemetry database
  -> Sunseeker website backend reads and prepares the latest data
  -> sunseekerwmu.org will display live vehicle information
```

After the database and website backend are available, select the `db` storage
mode, or `both` during a controlled migration, and configure the
`TELEMETRY_DB_*` environment variables described in
`docs/ONLINE_TELEMETRY_SCHEMA.md`. Do not enable this production path until the
team provides the database connection details. Database credentials must remain
on the telemetry computer and website backend. They must never be included in
browser JavaScript.

The public website is:

```text
https://sunseekerwmu.org
```

The public website URL is not an ingest or database URL. As part of the planned
deployment, the website backend should query the team database and publish a
safe read-only DTO for the live page.

### Option 2: HTTP Ingest API

Use this for development, a future API-based deployment, or another backend
that accepts telemetry over HTTPS.

```text
Telemetry app
  -> HTTPS POST to a configured ingest API
  -> Backend stores the event
  -> Website backend reads a public/latest endpoint
```

Example endpoint shapes are:

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

### Former Interim Solution: cagedmotion.com

Before the team-owned database method was produced, `cagedmotion.com` hosted an
IONOS Python CGI/MariaDB solution. Its endpoints were:

```text
POST https://cagedmotion.com/ingest-api/run_wsgi.py/telemetry
GET  https://cagedmotion.com/ingest-api/run_wsgi.py/api/telemetry/latest
```

These URLs are retained only to document the former solution and assist with
historical troubleshooting. They are not a currently configured source of live
information for `sunseekerwmu.org`.

## Planned Production Flow

```text
Telemetry app
  writes JSON telemetry to the team-owned database

Sunseeker website backend
  will read the latest telemetry and create a public-safe response

sunseekerwmu.org
  will display the latest vehicle information
```

## HTTP Endpoint Pattern (When HTTP Mode Is Used)

```text
POST /api/telemetry/ingest
GET  /api/telemetry/latest
```

The exact paths depend on the selected backend. Do not point the telemetry app
at the website root or a frontend page route.

Telemetry app settings:

```text
Storage mode: http
Ingest URL: https://your-api.example.com/api/telemetry/ingest
Payload format: legacy or dual
Auth mode: auto or X-API-Token
API token: same value as the ingest token on the server
Require JSON response: enabled
```

This is an optional HTTP configuration. The planned direct-database path for
`sunseekerwmu.org` is not currently configured.

The secret ingest API key should only exist in the Python telemetry app and on the backend. Do not put it in browser JavaScript.

## Auth Headers

The telemetry app can send the configured key as:

```text
Authorization: Bearer YOUR_API_KEY
X-API-KEY: YOUR_API_KEY
X-API-Token: YOUR_API_KEY
```

The `auto` auth mode sends all common headers for compatibility.

The telemetry app's `auto` auth mode sends the compatibility headers together.
The former IONOS CGI deployment used `X-API-Token` because it did not always
forward `Authorization`.

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

The planned team-owned database can store telemetry snapshots in the
`telemetry_events` table:

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

The browser should read through a safe endpoint supplied by the website
backend, for example:

```text
GET /api/telemetry/latest
```

That endpoint returns a smaller webpage-friendly object with `position`,
`speed`, `battery`, `race`, and `telemetry` sections.

## Reading Telemetry Data

The database must remain private. When the planned public latest read endpoint
is provided by the Sunseeker website backend, its conceptual path is:

```text
GET /api/telemetry/latest
```

The endpoint can then be used for:

- Live pages on `sunseekerwmu.org`
- Other websites/domains that need to display the car position
- Mobile/phone applications
- Small dashboards or map displays

Under the planned contract, no API token is required for public reads. Only
upload/ingest requests use `API_AUTH_TOKEN`.

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
  const response = await fetch('/api/telemetry/latest');

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
the website backend's `ALLOWED_ORIGINS` setting. Use `ALLOWED_ORIGINS=*` only
when the team intentionally wants unrestricted public browser access.

Example:

```env
ALLOWED_ORIGINS=https://sunseekerwmu.org,https://dashboard.example.com
```

Apply the change using the deployment procedure chosen for the future website
backend.

### Phone App Example

Phone apps can poll the public read endpoint without the ingest token:

```text
GET https://your-api.example.com/api/telemetry/latest
Accept: application/json
```

Recommended polling interval:

```text
Map/live UI: every 5-10 seconds
Background refresh: every 15-30 seconds
```

Avoid polling every second from many devices. Use a refresh interval appropriate
for the capacity of the website backend and database.

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

### Additional Future Read Endpoints

The initial planned read endpoint returns only the latest DTO. Add separate
public endpoints later if the website or phone app needs:

- Last 50 map points
- Battery history
- Race/lap history
- Vehicle-specific reads such as `/api/telemetry/latest?vehicle_year=2026`

## Smoke Test

For an HTTP-mode deployment, test the same path used by the telemetry app:

```bash
python3 event_smoke_test.py \
  --url https://your-api.example.com \
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

# Sunseeker Telemetry User Guide

This guide is for drivers, race strategists, array and battery engineers, and
other operators using the Sunseeker Telemetry application. It describes the
normal user workflow for application version 2.4.0.

The application receives live vehicle telemetry over a serial connection,
converts it into readable measurements, calculates additional operating
metrics, records CSV files, displays GPS race progress, and provides local
machine-learning predictions.

## Contents

1. [Important operating notes](#important-operating-notes)
2. [Installation and launch](#installation-and-launch)
3. [First-start configuration](#first-start-configuration)
4. [Race-day quick start](#race-day-quick-start)
5. [Main window and status header](#main-window-and-status-header)
6. [Dashboard](#dashboard)
7. [Graphs](#graphs)
8. [Data views](#data-views)
9. [GPS map and race operation](#gps-map-and-race-operation)
10. [Image annotation tools](#image-annotation-tools)
11. [CSV management and telemetry bundles](#csv-management-and-telemetry-bundles)
12. [Simulation](#simulation)
13. [Settings](#settings)
14. [Battery, array, and energy calculations](#battery-array-and-energy-calculations)
15. [Machine-learning predictions](#machine-learning-predictions)
16. [Weather and online telemetry](#weather-and-online-telemetry)
17. [End-of-day procedure](#end-of-day-procedure)
18. [Troubleshooting](#troubleshooting)
19. [Files and data locations](#files-and-data-locations)
20. [Glossary](#glossary)

## Important Operating Notes

The telemetry application is an engineering aid. It does not replace the
vehicle's safety systems, driver judgment, race regulations, or direct
measurement with calibrated equipment.

- Treat a stale, missing, or quality-flagged value as unavailable.
- Never make a safety-critical decision from an ML prediction alone.
- Array power is estimated from the high-voltage DC-bus balance; it is not a
  direct MPPT measurement.
- GPS distance, lap timing, and route progress depend on a valid GPS fix.
- Confirm the battery configuration before driving. An incorrect cell count,
  series count, or capacity makes remaining-energy calculations incorrect.
- Simulated telemetry is visibly marked and is not written into the real CSV
  history or ML training data.

## Installation and Launch

### Windows packaged application

1. Download the Windows release.
2. Keep the executable and its supporting files together.
3. Ensure there is a `config_files` folder beside the executable containing
   the battery configuration text files.
4. Connect the telemetry radio, CAN-to-serial device, or approved virtual COM
   port.
5. Start the executable.

The application creates an `application_data` folder for CSVs, settings,
models, and logs.

### Running from source

Python 3 and the packages in `requirements.txt` are required.

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src/main_app.py
```

Linux or macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/main_app.py
```

Run the source command from the project root so the application can find
`config_files` and `vehicle_years.txt`.

### Bench operation with a virtual serial port

The application still requires a valid serial-port name at startup, even when
you plan to use the Simulation tab.

On Linux, a paired pseudo-terminal can be created with:

```bash
socat -d -d pty,raw,echo=0 pty,raw,echo=0
```

Select one printed `/dev/pts/N` path in the application and send newline-ended
telemetry packets to the other path.

On Windows, use a paired virtual null-modem tool and select one side of the COM
pair in the application.

## First-Start Configuration

The Configuration dialog appears before the main window. Canceling it exits the
application.

### Battery Configuration

Select a battery configuration and press **Load Configuration**. A success
message confirms that it was loaded.

The battery file supplies:

- cell capacity in Ah;
- nominal cell voltage;
- total number of cells;
- number of cells in series.

The application uses those values to calculate total pack voltage, parallel
capacity, and total energy. Use the configuration for the car that is actually
connected.

To create a configuration from the application:

1. Select **Manual Input**.
2. Press **Load Configuration**.
3. Enter the requested cell capacity, cell voltage, cell quantity, and series
   count.
4. Enter a file name.
5. The application saves the new preset in `config_files`.

### Serial Connection

- **Select COM Port**: choose the vehicle telemetry port. The field is editable
  when a valid port path does not appear automatically.
- **Baud Rate**: must match the transmitting firmware. The normal choices are
  9600, 19200, 38400, 57600, and 115200.
- **Endianness**: must match the firmware's binary float byte order. An
  incorrect choice produces implausible numeric values.
- **Logging Level**: use `INFO` for normal operation and `DEBUG` temporarily
  when diagnosing packet or connection problems.

### Vehicle and Solcast

- **Vehicle Years** identifies the vehicle/run in stored settings and
  telemetry metadata.
- Choose **Add New** to add another vehicle year.
- Solcast API key, latitude, and longitude are optional, but the three fields
  must either all be supplied or all be blank.

Press **OK** only after the battery preset and serial port are correct.

## Race-Day Quick Start

Use this sequence at the start of an official session:

1. Connect and power the telemetry hardware.
2. Start the application.
3. Load the correct battery configuration.
4. Select the correct serial port, baud rate, and endianness.
5. Confirm that the header shows **Live** and **Connected**.
6. Wait for **Data age** to remain near zero.
7. Check the Dashboard for plausible pack voltage, current, SOC, temperatures,
   speed, GPS fix, and telemetry status.
8. Open **Map > Map setup**.
9. Select **FSGP Track** or **ASC Route**.
10. For FSGP, enter official lap length and race-day duration, set the timing
    line, then press **Reset Day** immediately before the official session.
11. For ASC, load the ordered GPX route files and press **Reset Day** at the
    start of the day.
12. Confirm the current Primary, Raw, and Training CSV locations under
    **Tools > CSV Management**.
13. Record race notes during the day so they can be included in the final
    telemetry bundle.

## Main Window and Status Header

The header provides three important indicators:

- **Mode**: `Live`, replay, or synthetic scenario.
- **Connection**: the active serial port or a stopped/error condition.
- **Data age**: seconds since the last telemetry update.

Data age is normal at up to 3 seconds, warned above 3 seconds, and treated as
dangerously stale above 10 seconds. If the value continues rising, do not trust
the displayed live values until the connection recovers.

The main tabs are:

- **Dashboard**
- **Graphs**
- **Data**
- **Map**
- **Tools**
- **Settings**

The application remembers window geometry and the last selected tabs.

## Dashboard

The Dashboard is the primary race-day cockpit. It collects the values an
operator is most likely to need without searching the detailed tables.

### Speed Source

Use **Speed Source** to select:

- **Nav**: the firmware-selected navigation speed.
- **Motor Avg**: the average velocity reported by both motor controllers.

Motor Avg requires both motor-controller velocity values. Compare the sources
when diagnosing GPS loss, wheel-speed disagreement, or drivetrain telemetry.

### Main Cards

The cards cover:

- vehicle speed;
- battery SOC, voltage, current, power, and temperature;
- maximum and minimum cell voltage;
- estimated array power and five-frame quality;
- PVS net amp-hours;
- motor temperatures and efficiency;
- remaining-time and break-even-speed predictions;
- GPS fix, lap count, lap timing, lap speeds, distance, day averages, and FSGP
  projection;
- telemetry health.

Double-click a metric card to choose an available unit override for that card.
The override is remembered. Global Metric/Imperial selection is available in
Settings.

### Operational Alerts

The alert list summarizes active:

- motor-controller errors or limits;
- invalid GPS;
- invalid or uncalibrated IMU data;
- malformed telemetry packets;
- machine-learning quality warnings.

**No active alerts** means the application has not identified a current
problem. It is not a substitute for the vehicle's safety checks.

## Graphs

Graphs are grouped into:

- **Motor Controller 1**
- **Motor Controller 2**
- **Battery Pack 1**
- **Battery Pack 2**
- **Remaining Capacity**
- **Insights**

Each graph page offers:

- **Window**: approximately the last 1, 3, 6, or 15 minutes at the normal
  update rate;
- **Pause/Resume**: freezes or resumes graph updates;
- **Clear**: clears in-memory graph history only;
- pointer hover: shows the graph value at a sample;
- graph double-click: toggles the graph's enlarged/zoomed view;
- Shift-double-click near the left axis: selects an available unit override.

The window labels are based on sample count, so they are approximate when
telemetry arrives faster or slower than one display update per second.

Graph colors can be changed under **Settings > Graph Colors**.

## Data Views

Open the **Data** tab for detailed telemetry.

### Data Table

The Data Table groups all supported values by subsystem. Columns show
Parameter, Value, and Unit.

- Red values indicate an active error/status field.
- Orange error counters indicate a nonzero count.
- Double-click a cell in the **Unit** column to select a per-field unit
  override.

Use this view to inspect array-estimate status and quality counters, navigation
diagnostics, raw motor/battery values, timestamps, weather, and ML flags.

### Custom Data Table

The Custom Data Table lets a crew create a compact role-specific display.

- Double-click a Parameter cell to replace that row's field.
- Double-click a Unit cell to change its unit.
- Right-click to add, rename, or remove groups and parameters.
- Use **Reset to Default** in the right-click menu to restore the initial
  layout.

The layout is saved as JSON and restored in later sessions.

### Data Display

Data Display is a scrolling, monospaced text view of formatted telemetry
snapshots. It is useful for broad inspection but is less compact than the table
or Dashboard.

## GPS Map and Race Operation

The Map tab combines vehicle position, map tiles, saved locations, route
progress, lap timing, distance, and race-day averages.

### Map controls

- Drag the map to pan.
- Use the on-map **+** and **-** buttons for fine zoom control.
- Enable **Follow vehicle** to keep the newest valid GPS position centered.
- Disable it to inspect another part of the route.
- Expand **Map setup** for controls.
- Expand **Race details** for full lap, distance, route, and tile status.
- The compact race summary remains visible while both drawers are collapsed.

Map tiles use OpenStreetMap and require internet access when the needed tiles
are not cached. GPS calculations can continue even when the background tiles
cannot load.

### Manual and saved locations

Enter a latitude from -90 to 90 and longitude from -180 to 180, then press
**Set** to preview that position. **Kalamazoo** returns to the built-in
Kalamazoo preview.

Use **Save** to name the current vehicle or manual location. **Go** returns to
the selected saved location, and **Delete** removes it. Saved locations persist
between sessions.

### FSGP Track mode

Use **FSGP Track** for circuit lap timing and official track mileage.

1. Select **FSGP Track**.
2. Enter the **Official lap length** in miles. Leave it at **Use GPS** only
   when an official distance is not available.
3. Enter the scheduled **Race-day duration** in hours to enable possible-lap
   projection.
4. Press **Set Start**, then double-click the first end of the start/finish
   timing line on the map.
5. Press **Set End**, then double-click the other end of the line.
6. The endpoints must be at least about 15 feet apart.
7. Press **Reset Day** at the official start.

The first valid crossing starts timing. Later valid crossings complete laps.
The timing line should cross the direction of travel rather than run along it.
Place it where GPS reception is reliable.

Lap protection rejects:

- crossings in the opposite direction;
- a new crossing until the car has moved at least 20 metres away from the
  timing line;
- lap times below 30 seconds;
- stationary movement below 1 mph.

These rules prevent GPS bouncing around start/finish from creating impossible
laps such as a 19-second circuit.

Average lap time and average completed-lap speed appear after at least three
completed laps. Official completed distance is:

```text
completed laps * entered official lap length
```

When official lap length is zero, filtered GPS lap distance is used instead.
The current partial lap is displayed but does not count as completed official
mileage.

The FSGP projection begins after at least three completed laps. It uses average
lap time, completed laps, current-lap progress, and scheduled time remaining.
It is a pace projection, not a guarantee.

### ASC Route mode

Use **ASC Route** for continuous point-to-point route progress.

1. Select **ASC Route**.
2. Press **Load GPX**.
3. Select one or more GPX files in travel order.
4. Each selected file becomes a route/checkpoint segment.
5. Press **Reset Day** at the official start.

The application reports:

- combined route name;
- current/next checkpoint segment;
- distance traveled and remaining;
- distance to the next checkpoint;
- checkpoint ETA at current speed.

ASC progress does not move backward when GPS jitters or the route doubles back.
Circuit lap timing is paused in ASC mode.

Changing between FSGP and ASC retains completed laps but discards the current
partial lap, because a partial circuit cannot be continued through a
point-to-point section.

### Trip and day controls

**Reset Trip** clears:

- filtered GPS trip distance;
- elapsed and moving-time averages;
- maximum speed;
- ASC route progress.

It does not clear completed lap results.

**Reset Day** clears the trip/day statistics, route progress, and lap results,
while retaining the placed timing line.

GPS trip distance excludes:

- movement reported below 1 mph;
- jumps that imply implausible travel for the reported speed and time;
- moving-time gaps longer than 5 seconds.

Overall day average uses distance divided by elapsed session time, so stops
lower it. Moving average uses only accepted moving time.

## Image Annotation Tools

Under **Tools**, the Battery Image and Array Image tabs can place temperature
or probe locations over a reference image.

1. Press **Load Image**.
2. Select the reference drawing or photograph.
3. Left-click the image to add probe points in the desired ID order.
4. Use **Undo** to remove the newest point.
5. Use **Clear Points** to remove all points.

Images and normalized point locations persist between sessions. The Battery
Image can associate incoming probe values with the placed IDs and identify the
hottest location.

## CSV Management and Telemetry Bundles

Open **Tools > CSV Management** to view the active file locations.

### CSV types

| File | Purpose |
| --- | --- |
| Primary CSV | Parsed, enriched telemetry, calculations, GPS/race fields, weather, and predictions |
| Secondary CSV | Timestamped raw serial lines for parser and firmware diagnosis |
| Training CSV | Sparse numeric rows used by the local ML models |

Primary CSV rows contain `csv_units_mode` and `csv_units_note`. Units can change
during a run, so downstream analysis should read the unit mode on each row.

### Available actions

- **Rename...** changes the active file name without changing its folder.
- **Save Primary CSV...** exports a copy of the parsed telemetry.
- **Save Secondary CSV...** exports a copy of the raw serial capture.
- **Change Save Folder...** moves the active CSV files to a selected folder and
  continues recording there.
- **Export Telemetry Bundle...** creates a portable ZIP.
- **Import Telemetry Bundle...** extracts a previously exported run.

Do not edit an active CSV with an application that locks the file. Export a
copy or a bundle and inspect the copy instead.

### Telemetry bundles

A bundle contains, when available:

```text
data/telemetry_data.csv
data/raw_hex_data.csv
data/training_data.csv
meta/metadata.json
meta/notes.txt
extras/telemetry_application.log
```

Use notes to record date, event, driver, vehicle, pack, array configuration,
weather, incidents, and any sensor problems.

When importing, choose whether to activate the imported run:

- **No** extracts it for inspection while leaving the live CSV destination
  unchanged.
- **Yes** switches active CSV storage to the imported run's directory. New
  live rows can then append to those active files.

Use **No** when you only want to review an old run.

## Simulation

Simulation is available under **Tools > Simulation**.

When simulation begins, live serial input is paused so real and simulated
packets cannot mix. The application resumes the prior serial connection when
simulation ends.

Simulated data:

- follows the normal parsing, calculation, GUI, GPS, and prediction path;
- is marked in the header;
- is not written to the live CSVs;
- is not added to ML training data;
- is not sent to the online telemetry service.

### Replay recorded telemetry

1. Browse to a Primary telemetry CSV.
2. Select playback speed from 0.1x to 10x.
3. Press **Start Replay**.

Replay uses the recorded timestamp gaps. `10x` runs at one tenth of the
recorded delay; `0.5x` takes twice as long.

### Synthetic scenarios

Choose:

- **Nominal Cruise**
- **High Load**
- **Charging Spike**
- **Custom**

The controls adjust duration, voltage, current, speed, temperature, and their
change over the scenario. **Speed multiplier** changes how quickly the scenario
runs.

Press **Stop Simulation** to stop either replay or a synthetic scenario.

## Settings

Press **Apply Settings** after changing normal connection, vehicle, display,
API, or Solcast fields.

### Connection

Configure:

- serial port;
- baud rate;
- endianness;
- Metric or Imperial display;
- logging level;
- vehicle year;
- driver name.

**Refresh Ports** rescans connected and virtual serial devices. Applying a new
port or baud rate restarts the live serial reader.

Changing global units updates the UI and future CSV output. Individual cards,
graphs, and data-table fields can still have their own saved unit overrides.

### API & Solar

The Telemetry Website/API section controls:

- ingest URL;
- optional API key;
- HTTP/database/both storage mode;
- authentication header style;
- legacy, IONOS, or dual payload format;
- whether a JSON response is required;
- session ID;
- vehicle identifier.

The ingest URL must start with `http://` or `https://`.

The Solcast section controls the API key and fallback coordinates. Enable
**Follow valid vehicle GPS every 5 minutes** to use the newest valid GPS
position for each weather poll. The manually configured location remains the
fallback.

### Models

- **Retrain Machine Learning Model** retrains the battery-life and break-even
  models from the active `training_data.csv`.
- **Add Training Data Files** merges selected historical CSV files into the
  normalized training corpus and retrains both models.

Do not retrain merely because a prediction looks unexpected. First inspect
sensor validity, quality flags, and the training-data operating range.

### Updates

Press **Refresh** to list available application versions. Select a version and
press **Install Selected** to download and apply it. Do not interrupt power or
close the application during the installation step.

### Graph Colors

Press **Choose** beside a telemetry field to select its graph color. Color
choices persist between sessions.

## Battery, Array, and Energy Calculations

### Battery current and power signs

For `BP_ISH_Amps`:

- positive current means pack discharge;
- negative current means pack charging or regenerative current;
- zero means idle.

`Battery_Power_Direction` presents the same interpretation in words.

The race-session shunt integrator uses real elapsed time and trapezoidal
integration. Negative current reduces previously used Ah, but remaining
capacity is never allowed above the configured physical pack capacity.
Telemetry gaps over 5 seconds are skipped instead of pretending the prior
current continued through the outage.

### PVS net amp-hours

`BP_PVS_milliamp*s` and `BP_PVS_Ah` are signed firmware counters. A negative
value is preserved and means net charging according to the firmware's sign
convention. It is valid data and is also retained in the ML training file.

The signed raw value is not capped. Only a derived physical remaining-capacity
value is bounded between empty and the configured total capacity.

### Estimated array power

There is no fixed wattage or array-area cap. This allows the same application
to support different array sizes, including future 6 square metre arrays.

Without a dedicated array-power sensor, the estimate is:

```text
array power ~= MC1 bus power + MC2 bus power - battery pack power
```

The estimate uses each source's reported bus voltage and current. It excludes
unmeasured auxiliary loads, so it can be lower than the array's true output.

For each firmware frame, the application requires synchronized:

- MC1 bus voltage/current;
- MC2 bus voltage/current;
- battery-shunt current;
- pack voltage.

Controller voltage must be within 25 percent of pack voltage. Missing inputs or
a voltage mismatch reject the frame instead of combining new and stale values.

Because controller and shunt sensors respond at different times, the
application averages five consecutive signed power-balance frames. The five
values are shown oldest to newest in **Array 5-Frame Inputs**. A short positive
spike can therefore be canceled by a later low or negative residual.

Useful quality fields are:

| Field | Meaning |
| --- | --- |
| `Array_Estimate_Status` | Stabilizing, estimated, or unavailable reason |
| `Array_Estimate_Window_Count` | Number of current synchronized samples, up to 5 |
| `Array_Estimate_Window_Spread_W` | Maximum minus minimum sample in the window |
| `Array_Estimate_Window_StdDev_W` | Within-window inconsistency |
| `Array_Estimate_Frame_Usable_Pct` | Percentage of complete synchronized frames |
| `Array_Estimate_Availability_Pct` | Percentage of attempts that published a five-frame estimate |
| `Array_Estimate_Frames_Rejected` | Frames not suitable for the window |
| `Array_Estimate_Missing_Telemetry_Count` | Rejections caused by missing inputs |
| `Array_Estimate_Voltage_Mismatch_Count` | Rejections caused by implausible bus-voltage disagreement |
| `Array_Estimate_Negative_Window_Count` | Five-frame averages that remained materially negative |

Interpret the estimate cautiously when availability is low or spread/standard
deviation is high. The estimate can be numerically high without being clipped;
use the quality fields to decide whether it is credible.

## Machine-Learning Predictions

The application uses two local scikit-learn random-forest regression models.

| Prediction | Inputs | Output |
| --- | --- | --- |
| Battery life | PVS milliamp-seconds, signed PVS Ah, and PVS voltage | Remaining runtime |
| Break-even speed | Available power and PVS voltage | Sustainable steady speed estimate |

The break-even model learns from measured steady-state driving. A training row
receives a break-even label only while:

- vehicle speed is at least 5 mph;
- IMU data is valid;
- absolute forward acceleration is no more than 0.03 g;
- measured motor bus power is positive.

This excludes acceleration and braking samples from the road-load curve.

After 20 new valid steady-state labels, the break-even model retrains in a
background batch. Predictions continue using the prior model until the
replacement is ready.

### Prediction quality

Always read the prediction together with:

- uncertainty;
- data age;
- `Prediction_Quality_Flags`.

`OK` means no known diagnostic problem was found. Other flags can indicate
missing data, nonnumeric data, stale values, an unfitted model, or inputs
outside the range seen during training.

The uncertainty is based on disagreement among the random-forest trees. It is
a warning indicator, not a guaranteed confidence interval.

### Array provenance for future ML

The exact five signed array-balance samples and the missingness/consistency
counters are retained in `training_data.csv`. They are provenance for auditing,
filtering, sample weighting, and a future supervised array model.

They are not automatically used as predictors in the current break-even model.
Without an independent array-power sensor, training on the calculated estimate
as its own truth would only teach a model to reproduce the same formula.

See [MACHINE_LEARNING.md](MACHINE_LEARNING.md) for the complete training and
validation details.

## Weather and Online Telemetry

### Solcast

With valid credentials and coordinates, Solcast data is polled every five
minutes. The live telemetry stream can include current weather plus 30-minute,
1-hour, and 24-hour forecast fields.

If GPS following is enabled, each poll uses the newest valid vehicle position.
If GPS is invalid, the configured coordinates are used.

### Online telemetry

Local UI and CSV recording operate independently from online upload. Online
snapshots are normally throttled to one send every 5 seconds.

An API failure should not stop local recording, but it is recorded in the log.
Check the ingest URL, network, authentication mode, payload format, and server
response settings when uploads fail.

Do not place API keys in exported notes, screenshots, or public issue reports.

## End-of-Day Procedure

1. Confirm the final lap, route, distance, and energy values are visible.
2. Open **Tools > CSV Management**.
3. Export a telemetry bundle with detailed notes.
4. If required, also save separate copies of the Primary and Secondary CSVs.
5. Verify that the ZIP opens and contains its `data`, `meta`, and `extras`
   entries.
6. Copy the bundle to the team's approved storage location.
7. Stop any running simulation.
8. Close the application.
9. Safely disconnect the telemetry hardware.

Do not rely on only one copy of race-day data.

## Troubleshooting

### Application will not pass the Configuration dialog

- Load a battery configuration before pressing OK.
- Connect a serial device, refresh ports, or type a valid virtual-port path.
- If Solcast is partially filled, supply key, latitude, and longitude or clear
  all three.

### Connected but no telemetry changes

- Confirm the header names the expected port and baud rate.
- Confirm the transmitter uses that port's paired endpoint.
- Verify every serial packet ends with a newline.
- Check firmware baud rate and endianness.
- Change log level to `DEBUG` and inspect the log.
- Review the Secondary CSV to see whether raw lines are arriving.

### Values are extremely large or nonsensical

- Verify Big Endian versus Little Endian.
- Verify firmware and desktop telemetry formats match.
- Inspect `Telemetry_Status`, `Telemetry_Error`, and the raw CSV.
- Confirm the correct battery and vehicle configuration.

### Data age keeps increasing

- Treat the displayed values as stale.
- Check radio/serial power, cable, port, and transmitter activity.
- Refresh ports and apply the correct connection settings.
- Restart the application if the operating system has reassigned the port.

### GPS map is blank or gray

- Check internet access for OpenStreetMap tiles.
- Expand Race details and inspect tile status.
- GPS, trail, and race calculations may still work over placeholder tiles.
- Confirm GPS valid, fix greater than zero, and nonzero coordinates.

### False or missing laps

- Put the timing line across the direction of travel.
- Make the line wide enough to tolerate GPS position error.
- Use a location with a reliable fix.
- A lap below 30 seconds is intentionally rejected.
- The vehicle must travel at least 20 metres away before the gate rearms.
- Wrong-direction crossings are intentionally rejected.

### FSGP projection says it is waiting

- Select FSGP Track.
- Enter a nonzero race-day duration.
- Press Reset Day at the official start.
- Complete at least three accepted laps.

### ASC progress is incorrect

- Load GPX files in travel order.
- Confirm each GPX contains at least two track, route, or waypoint points.
- Press Reset Trip or Reset Day before a new route attempt.
- Confirm valid GPS coordinates are close to the intended route.

### Array estimate is unavailable

Read `Array_Estimate_Status`.

- `Stabilizing`: wait for five consecutive synchronized frames.
- `missing telemetry`: inspect MC1BUS, MC2BUS, BP_ISH, and BP_PVS packets.
- `DC-bus voltage mismatch`: check stale controller data, scaling, and
  endianness.
- `averaged negative power balance`: inspect current signs, regenerative
  operation, and controller/shunt timing.

Do not solve an implausible estimate by adding a fixed wattage cap. Use the
synchronized inputs and quality counters to find the data problem.

### Prediction unavailable or implausible

- Read `Prediction_Quality_Flags`.
- Confirm the model files exist and the Training CSV contains valid rows.
- Check whether live inputs are outside the model's training range.
- Inspect uncertainty before using the result.
- Collect representative real driving data, then retrain.
- Do not add simulation data to the training corpus.

### CSV cannot be opened or moved

- Close other programs that may have locked the active file.
- Use **Save Primary CSV...** to create a review copy.
- Use **Change Save Folder...** from inside the application rather than moving
  active files manually.

### Where to find diagnostic logs

The main log is:

```text
application_data/telemetry_application.log
```

Rotated logs use numbered suffixes. Include the current log in a private
engineering handoff, but check it for server addresses or other sensitive
configuration before sharing publicly.

## Files and Data Locations

Normal runtime data is under `application_data`:

```text
application_data/
  config.json
  telemetry_application.log
  telemetry_data.csv
  raw_hex_data.csv
  training_data.csv
  combined_training_data.csv
  models/
    battery_life_model.pkl
    break_even_model.pkl
  imports/
```

Names can differ after using Rename or Change Save Folder.

Other persistent user data includes:

- battery presets in `config_files`;
- vehicle-year entries in `vehicle_years.txt`;
- image files and annotation state;
- GUI geometry, map preferences, saved locations, unit overrides, and custom
  table layout.

Back up `application_data`, `config_files`, and exported telemetry bundles when
moving the application to a new computer.

## Glossary

| Term | Meaning |
| --- | --- |
| Ah | Amp-hours, a measure of electric charge |
| ASC | American Solar Challenge point-to-point road event |
| BMS | Battery management system |
| DC bus | Shared high-voltage electrical connection among pack, array, and motor controllers |
| FSGP | Formula Sun Grand Prix circuit event |
| GPX | GPS Exchange Format route/track file |
| GHI/DNI/DHI/GTI | Solar irradiance measurements or forecasts |
| IMU | Inertial measurement unit |
| MC1/MC2 | Motor Controller 1 and Motor Controller 2 |
| ML | Machine learning |
| MPPT | Maximum power point tracker |
| PVS | Firmware photovoltaic/pack voltage and integrated-current telemetry |
| SOC | Battery state of charge |
| Telemetry bundle | ZIP containing run CSVs, metadata, notes, and the application log |
| Wh | Watt-hours, a measure of energy |

For raw packet names and all canonical fields, see
[TELEMETRY_FORMAT.md](TELEMETRY_FORMAT.md). For maintainers and developers, use
[START_HERE.md](START_HERE.md).

# Start Here

Use this page as the handoff map for a new maintainer.

## First Read

1. `README.md`
   - How to install, run, test with virtual serial ports, and use the main tabs.
2. `docs/USER_GUIDE.md`
   - Complete operator workflow, race modes, display interpretation, data
     export, ML use, and troubleshooting.
3. `docs/ARCHITECTURE.md`
   - How data moves through the app and which modules own each responsibility.
4. `docs/TELEMETRY_FORMAT.md`
   - What raw serial lines look like and how they become canonical telemetry fields.
5. `docs/MACHINE_LEARNING.md`
   - How prediction models are trained, saved, evaluated, and used at runtime.

## Common Tasks

| Task | Start With |
| --- | --- |
| Run the app from source | `README.md` |
| Operate the app on race day | `docs/USER_GUIDE.md` |
| Understand packet parsing | `docs/TELEMETRY_FORMAT.md`, then `src/data_processor.py` |
| Add a telemetry field | `src/key_name_definitions.py`, `src/data_processor.py`, `src/csv_handler.py` |
| Change GUI display groups | `src/gui_files/gui_display.py` and the relevant tab in `src/gui_files/` |
| Debug serial/PTY testing | `README.md` Linux virtual serial ports section |
| Debug buffering or CSV output | `src/buffer_data.py`, `src/csv_handler.py` |
| Debug HTTP/database telemetry | `docs/WEBSITE_INTEGRATION.md`, `docs/ONLINE_TELEMETRY_SCHEMA.md`, `docs/TELEMETRY_DB_SETUP.sql` |
| Work on predictions | `docs/MACHINE_LEARNING.md`, then `src/learning_datasets/`, `src/telemetry_application.py` |
| Work on simulation | `src/simulation.py`, Simulation section in `README.md` |

## Runtime Data Flow

```text
SerialReaderThread
  -> DataProcessor
  -> BufferData latest-known snapshot
  -> TelemetryApplication predictions + GPS/lap enrichment
  -> local CSV/training data
  -> GUI tabs
  -> online HTTP/database ingest every 5 seconds by default
```

Simulation uses the same processing/UI path, but it does not write real CSV rows
or send online telemetry.

## Important Conventions

- Use `TelemetryKey` values from `src/key_name_definitions.py` instead of hard-coded field strings.
- Add units to `TelemetryKey`; `KEY_UNITS` is generated from it.
- Keep GUI classes focused on display and user input. Put application actions in `TelemetryApplication` or a service module.
- Local CSV can be high rate. Online HTTP/database ingest is throttled by `TELEMETRY_ONLINE_SEND_INTERVAL_SECONDS`, default `5`.
- Website/browser code should read from a public backend endpoint, not directly from the protected ingest endpoint.

# Architecture

This project is a PyQt telemetry dashboard for live vehicle data, simulation replay, CSV export, machine-learning predictions, Solcast weather, and optional HTTP/database storage.

## Startup Path

`src/main_app.py` starts the Qt application and creates `TelemetryApplication`.

`src/telemetry_application.py` is the main orchestrator. It owns app startup, config handoff, the serial reader lifecycle, buffering, Solcast polling, simulation, ML prediction, GUI signal wiring, and telemetry storage handoff.

`src/app_settings.py` defines the canonical persisted settings names used in `application_data/config.json`. New config fields should be added to the `AppSettings` dataclass first, then read by the UI/application layer.

## Data Flow

1. `SerialReaderThread` in `src/serial_reader.py` reads raw serial lines.
2. `DataProcessor` in `src/data_processor.py` parses raw telemetry formats into canonical `TelemetryKey` field names.
3. `TelemetryApplication.process_data()` adds a timestamp and pushes parsed data into `BufferData`.
4. `BufferData` creates complete latest-known snapshots from partial packet updates.
5. `TelemetryApplication` adds prediction, GPS route, lap timing, and static battery fields.
6. Non-simulation snapshots are written to local CSV/training data.
7. The enriched snapshot is emitted to every GUI tab.
8. Online HTTP/database storage receives throttled snapshots every 5 seconds by default.

## Main Modules

- `src/main_app.py`: Qt process entry point.
- `src/telemetry_application.py`: application orchestration.
- `src/app_settings.py`: config key names, defaults, validation, load/save helpers.
- `src/data_processor.py`: raw serial line parser.
- `src/key_name_definitions.py`: canonical telemetry field names and units.
- `src/buffer_data.py`: packet buffering and snapshot flushing.
- `src/csv_handler.py`: CSV output, training data, and telemetry bundles.
- `src/db_writer.py`: database storage.
- `src/simulation.py`: replay and synthetic telemetry generation.
- `src/gui_files/`: PyQt tabs and dialogs.
- `src/learning_datasets/`: prediction models and diagnostics. See `docs/MACHINE_LEARNING.md` for model inputs, targets, retraining, and interpretation.

## GUI Boundaries

GUI classes should display state, gather user input, and emit signals. Application actions such as serial restart, Solcast refresh, HTTP sending, CSV import/export, and model retraining should stay in `TelemetryApplication` or a dedicated service module.

## Storage Boundaries

CSV file mechanics are handled by `CSVHandler`; snapshot assembly is handled by `BufferData`; final enriched CSV writes are coordinated by `TelemetryApplication`. HTTP/API sending is currently in `TelemetryApplication` and should move to a future `telemetry_sender.py` when that file is split. Database writing already lives behind `TelemetryDBWriter`.

## Suggested Future Split

`telemetry_application.py` still carries several responsibilities. A lower-risk split would be:

```text
telemetry_application.py     app orchestration and Qt signal wiring
telemetry_sender.py          HTTP/API payload + POST logic
app_settings.py              config.json load/save and settings validation
solcast_client.py            Solcast fetch logic
serial_controller.py         serial thread start/stop/restart
```

Keep the public behavior unchanged while extracting one responsibility at a time.

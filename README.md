# Telemetry Application

A cross-platform telemetry dashboard built for the Sunseeker Solar Car team. The app ingests live CAN/serial traffic from the vehicle, converts it into human-friendly metrics, and visualises everything through an extensible PyQt interface. It bundles a machine-learning layer for energy predictions, supports portable data exports, and now includes a simulation mode so engineers can rehearse race-day scenarios without the car.

---

## Platform Setup & Launch

### Windows (packaged executable)
1. Download the latest release from GitHub (the `.exe` file plus the two battery configuration `.txt` files).  
2. Place the executable and the two config files in the same directory, keeping the config files under a folder named `config_files`.  
3. Run the executable. On first launch the app creates two CSVs and one rotating log file inside `application_data/`. Logs rotate up to five times at 20 MB each so you always have fresh diagnostics.

### macOS / Linux (source)
1. Clone or download the repository.  
2. Open a terminal in the project root.  
3. Create/activate a Python environment (`python3 -m venv .venv && source .venv/bin/activate`).  
4. Install requirements (`pip install -r requirements.txt`).  
5. Launch with `python src/main_app.py`.

---

## Key Tabs & Features

### Data Display & Data Tables
Real-time telemetry values grouped by subsystem (motor controllers, battery packs, solar data, etc.). Predictions such as remaining time and break-even speed are annotated with uncertainty bands, timestamps, and quality flags.

### Graph Tabs
PyQtGraph-powered plots for motor controllers, battery packs, remaining capacity, and the “Insights” panel (efficiency, power, imbalance metrics). Colours can be customised and persisted through the settings tab.

### Image Annotation Tabs
Battery and array image tabs let you overlay probe points on reference drawings. Points and images persist between sessions (`src/application_data/user_images/` and `config.json`). Use Clear/Undo to refine placements.

### CSV Management
Quick access to current CSV locations, shortcuts to export copies, and controls to change the capture directory. From this tab you can now create “Telemetry Bundles” (zip archives with data, notes, metadata, and logs) and import previous runs for offline analysis.

### Simulation
Replay recorded telemetry CSVs or generate synthetic scenarios (Nominal Cruise, High Load, Charging Spike). Simulation data streams through the UI but is intentionally **not** written back to CSVs or sent to the telemetry server, so your historical data stays clean.

### Settings
Configure COM port, baud rate, log level, Solcast credentials, unit system, and colour themes. Includes machine-learning retrain controls, Solcast key management, and an integrated updater to install tagged releases.

---

## Battery Configuration Files

To add new battery pack presets to the configuration dialog:
1. Create a `.txt` file with the following lines and numeric values:
   - `Battery cell capacity amps hours`
   - `Battery cell nominal voltage`
   - `Amount of battery cells`
   - `Number of battery series`
2. Save the file inside the `config_files` folder next to the executable (or project root when running from source).
3. The entry appears in the configuration dropdown the next time the app starts.

---

## Developer Notes

### Code Map
- `main_app.py` – entry point; wires logging and launches `TelemetryApplication`.
- `telemetry_application.py` – central coordinator: GUI creation, serial reader lifecycle, buffering, ML predictions, telemetry server upload, and simulation handling.
- `buffer_data.py` / `csv_handler.py` – ingest buffering, CSV/training persistence, and bundle import/export helpers.
- `learning_datasets/` – machine-learning pipelines and quality diagnostics.
- `gui_files/` – modular PyQt tabs (data display, graphs, images, simulation, settings, CSV management).
- `simulation.py` – worker threads for replaying recorded telemetry and generating synthetic scenarios.

### Building & Releases
1. Run unit/system smoke tests locally (e.g., simulation replay, bundle export/import).  
2. Update `Version.py` and changelog.  
3. Tag the release (`git tag vX.Y.Z`) and push; the GitHub Actions workflow builds Windows/macOS/Linux artifacts via PyInstaller, runs `scripts/build_tuf_repo.py`, and publishes signed assets plus TUF metadata.  
4. Verify telemetry bundles and updater metadata before announcing.

### Updating the Updater
The application uses TUF for signed updates. When publishing new artifacts, ensure you upload the freshly generated `release/metadata/*.json` and `release/targets/*.tar.gz`. Timestamp validity defaults to 60 days; rerun the pipeline for each release.

### Simulation & Data Integrity
Simulated data never touches the on-disk CSVs or training corpus and is not forwarded to the remote ingestion endpoint. The core buffer pipeline still runs so derived metrics and predictions remain accurate during dry runs. When the simulation finishes, the app automatically resumes the serial reader if it was running before.

### Troubleshooting
- Logs live under `application_data/telemetry_application.log` with rotation to `*.1` … `*.5` at 20 MB each.  
- Use the Simulation tab to reproduce edge cases without hardware.  
- Enable higher log levels via the settings tab (`DEBUG`) for verbose packet tracing.  
- The machine-learning layer relies on `training_data.csv`; ensure it has valid numeric entries before retraining.

---

## Contributing
1. Fork the repository and create a feature branch.  
2. Keep changes modular (GUI tabs, CSV handler, ML pipelines, simulation).  
3. Update the README or docs if you modify user-facing flows.  
4. Run `python -m compileall src` (already part of CI) and any project-specific tests.  
5. Submit a pull request with a concise summary plus validation steps.

Thanks for keeping the telemetry stack thriving for future Sunseeker crews!

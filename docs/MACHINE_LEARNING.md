# Machine Learning Predictions

The telemetry application includes a small local machine-learning layer for
race-day energy predictions. It is intentionally conservative: the models are
trained from the local `training_data.csv`, saved on disk as `joblib` files, and
only use a few stable telemetry fields rather than the full live snapshot.

The implementation lives in `src/learning_datasets/machine_learning.py`. The
application wires it into live processing from `src/telemetry_application.py`,
and training rows are written by `src/buffer_data.py`.

## What The Models Predict

There are two independent regression models:

| Model | Runtime output | Target column | Feature columns |
| --- | --- | --- | --- |
| Battery life | `Predicted_Remaining_Time` | `Used_Ah_Remaining_Time` | `BP_PVS_milliamp*s`, `BP_PVS_Ah`, `BP_PVS_Voltage` |
| Break-even speed | `Predicted_BreakEven_Speed` | `BreakEvenSpeed` | `BreakEven_Power_W`, `BP_PVS_Voltage` |

The battery-life model estimates remaining runtime in hours. The app also
formats this into `Predicted_Exact_Time` with the existing exact-time helper.

The break-even model learns the car's steady-state road-load curve. Training
examples are collected while the car is moving at least 5 mph, IMU data is
valid, and absolute forward acceleration is at most 0.03 g. Each example pairs
measured total motor-controller bus power with observed speed. At runtime,
synchronized net array power is placed into the same power feature to estimate
the speed that available solar power can sustain. Acceleration and braking rows
are stored without a break-even label and cannot train this model.

## How Prediction Runs

1. Live serial data is parsed into canonical telemetry fields.
2. `BufferData` builds a latest-known complete snapshot from recent packets.
3. `TelemetryApplication.process_data()` extracts only the model features from
   that snapshot.
4. `MachineLearningModel` predicts battery life and break-even speed.
5. The app writes prediction values, uncertainty values, data age, and quality
   flags back into the combined telemetry snapshot.
6. Non-simulation snapshots are written to CSV and sent to the GUI/server.

Simulation replay uses the same prediction path so the UI behaves realistically,
but simulation data is not written into the real CSVs or training corpus.

## Model Type

Both predictors use scikit-learn `RandomForestRegressor` models. Battery life
retains its five-row moving-average preprocessing. Break-even consumes the
already synchronized and smoothed array-power estimate directly:

```text
Battery:    MovingAverage(window=5) -> RandomForestRegressor
Break-even: RandomForestRegressor(BreakEven_Power_W, BP_PVS_Voltage)
```

The battery random forest uses `min_samples_leaf=5`; break-even uses
`min_samples_leaf=3`. Both use:

```text
n_estimators=100
random_state=42
```

Random forests are a practical fit here because they are actual supervised
machine-learning models that handle non-linear
relationships without needing much feature scaling or hand tuning. They are
also easy to save, load, and inspect locally.

Break-even training requires at least 20 steady-state rows. The last 20% of
rows are held out chronologically to calculate validation MAE and R-squared;
the production model is then refit on all valid rows. Validation results, row
count, feature ranges, label definition, and training time are saved with the
model.

## Uncertainty And Quality Flags

For each prediction, the app also estimates ensemble spread across the random
forest trees:

```text
sigma = standard deviation of individual tree predictions
uncertainty = 1.96 * sigma
```

This is not a formal guarantee, but it is useful as a warning signal. Larger
uncertainty means the trees disagree more.

The saved model metadata also records the feature min/max range seen during
training. At runtime, `QualityDiagnostics` uses this metadata to flag:

- missing model features
- non-numeric model features
- out-of-range model inputs
- stale data
- unfitted models
- prediction errors

These flags are written to `Prediction_Quality_Flags`. `OK` means no known
diagnostic issue was detected for that snapshot.

`BP_PVS_Voltage` has a known operational lower bound of 100 V for quality
diagnostics. A narrow training dataset with a higher minimum voltage does not
produce an out-of-range warning until live voltage falls below 100 V. The
training maximum is still enforced; a model genuinely trained below 100 V
retains that wider observed range.

## Training Data

The app maintains a sparse training file named `training_data.csv`. By default
it lives in the active application data directory managed by `CSVHandler`.

The required headers are:

```csv
BP_PVS_milliamp*s,BP_PVS_Ah,BP_PVS_Voltage,Used_Ah_Remaining_Time,Array_Estimated_Power_W,BreakEven_Power_W,BreakEvenSpeed
```

Battery-life rows are written when its required values are present and numeric.
The array-power column may be unavailable during stabilization, and the
break-even power/target remain `N/A` unless the row passes the steady-state gate:

- `BP_PVS_milliamp*s`: integrated PV current signal in milliamp-seconds
- `BP_PVS_Ah`: integrated PV current converted to amp-hours
- `BP_PVS_Voltage`: PV/battery-pack voltage used by the model
- `Used_Ah_Remaining_Time`: calculated remaining time target, in hours
- `Array_Estimated_Power_W`: synchronized five-frame array-power feature
- `BreakEven_Power_W`: measured total motor-controller bus power for a valid
  steady-state training row; at prediction time this feature receives current
  net array power
- `BreakEvenSpeed`: observed speed only for a moving, steady-state sample;
  otherwise `N/A`

The training file deliberately excludes most display-only telemetry fields.
Keeping the model input narrow reduces accidental coupling to GUI fields and
makes it easier to understand why a prediction changed.

## How To Train From The App

1. Run the app against live telemetry long enough to collect representative
   `training_data.csv` rows.
2. Open **Settings > Models**.
3. Click **Retrain Machine Learning Model**.
4. Confirm the dialog.
5. Wait for the success or failure message.

Manual retraining remains available, but live operation also counts new valid
break-even labels. After 20 new steady-state examples, the break-even forest
re-trains in a background thread and atomically replaces the live model. This
is periodic batch learning because scikit-learn random forests do not support
incremental `partial_fit`; predictions continue using the prior model while the
replacement is trained.

Retraining calls:

```text
train_battery_life_model(training_data.csv)
train_break_even_model(training_data.csv)
```

The trained models are saved under the active CSV/application data directory:

```text
<active-data-directory>/models/battery_life_model.pkl
<active-data-directory>/models/break_even_model.pkl
```

On startup, the app first tries to load these saved models. If a model is
missing or cannot be loaded, it attempts to retrain from the available
`training_data.csv`.

## Training With Additional CSV Files

The settings UI can also emit a retrain request with additional CSV files.
Those files are combined with the current `training_data.csv`, normalized into
the seven training columns, written to `combined_training_data.csv`, and both
models are retrained from the combined data. After both models train
successfully, the same normalized merged rows are promoted back into
`training_data.csv`.

Use this when merging prior runs, test sessions, or corrected labels. The
additional files can be either sparse training CSVs or fuller telemetry CSVs.
For full telemetry CSVs, the combiner can derive `BreakEvenSpeed` from the first
available speed field below, but only on rows with positive motor bus power,
speed of at least 5 mph, valid IMU data, and absolute forward acceleration no
greater than 0.03 g:

```text
MC1VEL_Speed
MC1VEL_Velocity
NAV_VEHICLE_MPH
NAV_GPS_MPH
NAV_IMU_MPH
```

Every selected file is parsed independently. Missing files, unreadable CSVs,
missing required columns, and non-numeric/incomplete rows are skipped with log
messages. If no valid rows remain, no `.pkl` files are replaced.

After a successful combined retrain, the files have these roles:

| File | Role |
| --- | --- |
| `combined_training_data.csv` | Snapshot of the merged normalized data used for that retrain |
| `training_data.csv` | Ongoing master training corpus; future live rows append here |
| `battery_life_model.pkl` / `break_even_model.pkl` | Saved models trained from the merged data |

This means a user can import older telemetry once, retrain, and keep driving.
New valid rows from the current day append to the merged `training_data.csv`.
Break-even retraining occurs automatically in 20-label batches; normal manual
retraining still uses the historical imported data plus newly gathered rows.

## Data Quality Checklist Before Training

Before trusting a freshly trained model, check the training file:

- It has the exact required headers.
- The required columns contain numeric values, not display text such as `N/A`.
- The data covers the expected operating range: low/high PV current, voltage
  variation, slow/fast speeds, clouds, charging, and sustained driving.
- Rows are from real telemetry, not simulation replay.
- The label columns are meaningful for the question being asked.
- Obvious startup/shutdown transients are removed if they do not represent
  normal driving.

A model trained on a narrow bench session can still predict, but the
out-of-range flags and uncertainty values should be treated seriously.

## Command-Line Training Option

The GUI is the normal workflow, but developers can retrain from a Python shell
or short script:

```python
from src.learning_datasets.machine_learning import MachineLearningModel

data_dir = "application_data"  # Replace with the active CSV directory if changed.
model = MachineLearningModel(model_dir=f"{data_dir}/models")
model.train_battery_life_model(f"{data_dir}/training_data.csv")
model.train_break_even_model(f"{data_dir}/training_data.csv")
```

Run this from the repository root with the project virtual environment active.
The output `.pkl` files can then be used by the app on the next launch, as long
as they are written to the same data directory the app is using.

## Interpreting Results

Use the prediction value and quality fields together:

| Field | Meaning |
| --- | --- |
| `Predicted_Remaining_Time` | Estimated remaining runtime in hours, or `Prediction unavailable` |
| `Predicted_Exact_Time` | Remaining runtime formatted as `hh:mm:ss`, or `N/A` |
| `Predicted_Remaining_Time_Uncertainty` | Approximate 95 percent uncertainty band in hours |
| `Predicted_BreakEven_Speed` | Estimated break-even-speed label in mph, or `Prediction unavailable` |
| `Predicted_BreakEven_Speed_Uncertainty` | Approximate 95 percent uncertainty band in mph |
| `Prediction_Data_Age_s` | Age of the telemetry snapshot used for prediction |
| `Prediction_Quality_Flags` | Semicolon-separated diagnostics, or `OK` |

If a prediction is unavailable, the most common causes are missing features,
non-numeric feature values, missing training data, or an unfitted model file.

## Improving The Models Later

Good next improvements would be:

- Add route/weather features only after they are stable and consistently
  present in the training data.
- Add a small CLI retraining script that prints data coverage and model quality
  before replacing the current `.pkl` files.

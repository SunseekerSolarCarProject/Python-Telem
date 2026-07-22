# src/learning_datasets/machine_learning.py

"""
MachineLearningModel for solar-car telemetry:
 1. Battery life prediction using integrated PV current
 2. Break-even speed prediction from the learned steady-state road-load curve

The app trains these models locally from training_data.csv and stores the fitted
pipelines as .pkl files beside the active application data. Runtime prediction
returns both a value and diagnostics so the GUI can display "unavailable",
uncertainty, stale/unfitted flags, or out-of-range warnings without guessing.
"""

import os
import logging
import threading
import joblib
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.exceptions import NotFittedError
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.utils.validation import check_is_fitted
from sklearn.base import TransformerMixin, BaseEstimator


class MovingAverage(TransformerMixin, BaseEstimator):
    """
    Rolling-average smoother over `window` rows for specified columns.

    This is a scikit-learn transformer so the smoothing step is saved inside the
    same Pipeline as the random forest. At runtime a single-row prediction still
    passes through this transformer; min_periods=1 keeps that case valid.
    """
    def __init__(self, window: int = 50, cols: list = None):
        self.window = window
        self.cols = cols or []

    def fit(self, X, y=None):
        # No learned state is needed; the transformer only smooths incoming rows.
        return self

    def transform(self, X):
        # Work on a copy so callers do not see their feature DataFrame mutated.
        df = X.copy()
        for c in self.cols:
            df[c] = df[c].rolling(self.window, min_periods=1).mean()
        return df


class MachineLearningModel:
    """
    Encapsulates both:
      - Battery life:   RF([PV_Ah, PV_V]) -> Used_Ah_Remaining_Time
      - Break-even:     RF([propulsion power, pack V]) -> sustainable speed
    """
    # The canonical sparse training schema. Full telemetry CSVs are normalized
    # down to exactly these columns before training model artifacts.
    TRAINING_COLUMNS = [
        'BP_PVS_milliamp*s',
        'BP_PVS_Ah',
        'BP_PVS_Voltage',
        'Used_Ah_Remaining_Time',
        'Array_Estimated_Power_W',
        'BreakEven_Power_W',
        'BreakEvenSpeed',
    ]
    # Full telemetry exports may not have BreakEvenSpeed yet. These fields are
    # accepted, in priority order, as the current speed label for that target.
    BREAK_EVEN_LABEL_ALIASES = [
        'MC1VEL_Speed',
        'MC1VEL_Velocity',
        'NAV_VEHICLE_MPH',
        'NAV_GPS_MPH',
        'NAV_IMU_MPH',
    ]
    # A narrow training run may never observe the lower end of the vehicle's
    # normal pack-voltage range. Do not report PVS voltage extrapolation until
    # it falls below this known operational floor.
    PVS_VOLTAGE_QUALITY_MIN = 100.0
    BREAK_EVEN_FEATURES = ['BreakEven_Power_W', 'BP_PVS_Voltage']
    BREAK_EVEN_MODEL_VERSION = 2
    MIN_BREAK_EVEN_TRAINING_ROWS = 20
    MIN_BREAK_EVEN_SPEED_MPH = 5.0
    STEADY_STATE_MAX_ABS_FORWARD_G = 0.03

    def __init__(self, model_dir: str = None):
        # --- Logger ---
        self.log = logging.getLogger(self.__class__.__name__)
        self.log.setLevel(logging.INFO)
        self._model_lock = threading.RLock()
        self._training_lock = threading.Lock()

        # --- Model directory & paths ---
        base = os.path.dirname(os.path.abspath(__file__))
        if model_dir is None:
            # Default back-compat: sibling "models" folder next to this file.
            # Normal app startup passes <active-data-dir>/models instead.
            model_dir = os.path.join(base, 'models')
        os.makedirs(model_dir, exist_ok=True)

        self.batt_path = os.path.join(model_dir, 'battery_life_model.pkl')
        self.be_path   = os.path.join(model_dir, 'break_even_model.pkl')

        # --- Build pipelines ---
        self._build_battery_pipeline()
        self._build_break_even_pipeline()

        # --- Metadata holders for diagnostics ---
        # Metadata is saved beside the pipeline so predictions can report
        # whether a live feature is outside the range seen during training.
        self.batt_meta: dict = {}
        self.be_meta: dict = {}

        # --- Load or train on startup ---
        # Startup should prefer existing fitted .pkl files. If a model is
        # missing/corrupt and training_data.csv exists, attempt a local rebuild.
        self._load_or_train(self.batt_pipe, self.batt_path, self.train_battery_life_model, self.batt_meta)
        self._load_or_train(
            self.be_pipe,
            self.be_path,
            self.train_break_even_model,
            self.be_meta,
            expected_model_version=self.BREAK_EVEN_MODEL_VERSION,
        )


    def _load_model_bundle(self, obj):
        """
        Normalize joblib payloads so we can support legacy pipeline-only dumps
        as well as newer {pipeline, meta} bundles.
        """
        meta: dict = {}
        pipeline = obj
        if isinstance(obj, dict):
            # Older files may have used different keys; accept all known shapes
            # so crews can carry model files forward across releases.
            pipeline = obj.get('pipeline') or obj.get('model') or obj.get('pipeline_') or obj
            meta = obj.get('meta') or {}
        return pipeline, meta


    def _load_or_train(
        self,
        pipe: Pipeline,
        path: str,
        train_fn,
        meta_target: dict,
        expected_model_version: int | None = None,
    ):
        """
        If a fitted model exists at `path`, load it.
        Otherwise, retrain by calling `train_fn(...)` on training_data.csv.
        """
        if os.path.exists(path):
            try:
                loaded = joblib.load(path)
                pipeline, meta = self._load_model_bundle(loaded)
                if (
                    expected_model_version is not None
                    and meta.get("model_version") != expected_model_version
                ):
                    raise ValueError(
                        f"Model version {meta.get('model_version')} is incompatible with "
                        f"required version {expected_model_version}"
                    )
                check_is_fitted(pipeline)
                # Replace pipeline steps in place so existing object references
                # remain valid for the application.
                pipe.steps[:] = pipeline.steps
                meta_target.clear()
                if isinstance(meta, dict):
                    meta_target.update(meta)
                self.log.info(f"Loaded fitted model from {path}")
                return
            except Exception:
                self.log.warning(f"Could not load fitted model at {path}; retraining.")
        # Retrain if a CSV is available near the model directory. Normal app
        # runs store models under <data-dir>/models and training_data.csv in
        # <data-dir>; keep the legacy application_data candidate as a fallback.
        model_parent = os.path.abspath(os.path.join(os.path.dirname(path), '..'))
        candidates = [
            os.path.join(model_parent, 'training_data.csv'),
            os.path.join(model_parent, 'application_data', 'training_data.csv'),
        ]
        for td in candidates:
            if os.path.exists(td) and os.path.getsize(td) > 0:
                # train_fn handles required-column checks and returns a success
                # flag; startup only needs to make a best-effort attempt.
                train_fn(td)
                return
        self.log.warning(f"No training_data.csv found near {os.path.dirname(path)} to train model.")


    def _clean_data(self, df: pd.DataFrame, cols: list) -> pd.DataFrame:
        """
        Replace infinities with NaN and drop any rows lacking required columns.
        """
        # scikit-learn cannot fit on NaN/Inf in these pipelines, so treat
        # non-finite values like missing data and drop incomplete training rows.
        df = df.replace([np.inf, -np.inf], np.nan)
        return df.dropna(subset=cols)


    # -------------------------------------------------------------------------
    # SECTION: BATTERY LIFE PIPELINE
    # -------------------------------------------------------------------------
    def _build_battery_pipeline(self):
        """
        Pipeline:
          - smooth PV_mA_s, PV_Ah, PV_V
          - RandomForestRegressor
        """
        self.batt_pipe = Pipeline([
            ('smooth', MovingAverage(window=5, cols=[
                'BP_PVS_milliamp*s',
                'BP_PVS_Ah',
                'BP_PVS_Voltage'
            ])),
            ('rf', RandomForestRegressor(
                # A modest forest keeps retraining responsive from the GUI while
                # still giving enough trees for a useful ensemble spread.
                n_estimators=100,
                min_samples_leaf=5,
                random_state=42
            )),
        ])


    def _collect_feature_ranges(self, df: pd.DataFrame, feats: list[str]) -> dict:
        """Capture min/max feature ranges for out-of-range runtime diagnostics."""
        ranges: dict[str, tuple[float, float]] = {}
        for col in feats:
            series = df[col]
            if series.empty:
                continue
            ranges[col] = (float(series.min()), float(series.max()))
        return ranges


    def _diagnostic_feature_range(self, feature: str, feature_range) -> tuple[float, float]:
        """Return the accepted range used only for runtime quality warnings."""
        minimum, maximum = feature_range
        if feature == 'BP_PVS_Voltage':
            minimum = min(float(minimum), self.PVS_VOLTAGE_QUALITY_MIN)
        return float(minimum), float(maximum)


    def _target_stats(self, y: pd.Series) -> dict:
        """Store simple target stats for future diagnostics/reporting."""
        if y.empty:
            return {"mean": 0.0, "std": 0.0}
        std = float(y.std(ddof=0)) if len(y) > 1 else 0.0
        return {
            "mean": float(y.mean()),
            "std": std,
        }


    def train_battery_life_model(self, csv_path: str):
        """
        Train battery-life model:
          features = [ 'BP_PVS_milliamp*s', 'BP_PVS_Ah', 'BP_PVS_Voltage' ]
          target   =   'Used_Ah_Remaining_Time'
        """
        df = pd.read_csv(csv_path)
        feats  = ['BP_PVS_milliamp*s', 'BP_PVS_Ah', 'BP_PVS_Voltage']
        target = 'Used_Ah_Remaining_Time'

        missing = [c for c in feats + [target] if c not in df.columns]
        if missing:
            # Returning a falsey value lets the GUI report a failed retrain
            # instead of silently continuing with stale model files.
            self.log.error(f"Battery-life CSV missing columns: {missing}")
            return

        df = self._clean_data(df, feats + [target])
        if df.empty:
            self.log.error("Battery-life training skipped: no valid numeric rows after cleaning.")
            return False
        X = df[feats]
        y = df[target]

        # Fit the complete preprocessing+forest pipeline so the saved artifact
        # exactly matches the runtime prediction path.
        self.batt_pipe.fit(X, y)
        meta = {
            "feature_ranges": self._collect_feature_ranges(X, feats),
            "target_stats": self._target_stats(y),
            "trained_at": datetime.now(timezone.utc).isoformat(timespec='seconds'),
        }
        # Save both the fitted pipeline and its metadata together. Legacy loaders
        # still accept pipeline-only dumps, but metadata powers quality flags.
        joblib.dump({"pipeline": self.batt_pipe, "meta": meta}, self.batt_path)
        self.batt_meta.clear()
        self.batt_meta.update(meta)
        self.log.info(f"Trained battery-life model -> {self.batt_path}")
        return True


    def predict_battery_life_details(self, data: dict) -> dict:
        """
        Predict remaining time (hours) given:
          data['BP_PVS_milliamp*s'],
          data['BP_PVS_Ah'],
          data['BP_PVS_Voltage']
        """
        feats = ['BP_PVS_milliamp*s', 'BP_PVS_Ah', 'BP_PVS_Voltage']
        details = {
            # Keep the prediction response structured. TelemetryApplication can
            # display a best effort value while QualityDiagnostics expands flags.
            "prediction": None,
            "uncertainty": None,
            "sigma": None,
            "missing_features": [],
            "invalid_features": [],
            "out_of_range": {},
        }

        missing = [k for k in feats if k not in data]
        if missing:
            self.log.error(f"Missing features for battery-life: {missing}")
            details["missing_features"] = missing
            return details

        values = []
        invalid = []
        for k in feats:
            try:
                # Convert every feature explicitly so strings from CSV/replay
                # behave the same as numeric live telemetry values.
                values.append(float(data[k]))
            except (TypeError, ValueError):
                invalid.append(k)
        if invalid:
            self.log.error(f"Invalid (non-numeric) features for battery-life: {invalid}")
            details["invalid_features"] = invalid
            return details

        row = pd.DataFrame([values], columns=feats)
        try:
            pred, sigma = self._predict_with_uncertainty(self.batt_pipe, row)
        except NotFittedError:
            self.log.warning("Battery-life model not fitted yet, skipping prediction.")
            details["not_fitted"] = True
            return details
        except Exception as e:
            self.log.error(f"Error predicting battery-life: {e}")
            details["error"] = str(e)
            return details

        details["prediction"] = pred
        details["sigma"] = sigma
        # 1.96*sigma is an approximate 95% band from tree disagreement. It is a
        # warning signal, not a strict statistical guarantee.
        details["uncertainty"] = 1.96 * sigma if sigma is not None else None

        ranges = self.batt_meta.get("feature_ranges", {}) if isinstance(self.batt_meta, dict) else {}
        outliers = {}
        for col, value in row.iloc[0].items():
            # Flag extrapolation beyond the training feature envelope. The model
            # can still predict, but the GUI should show caution.
            rng = ranges.get(col)
            if rng:
                mn, mx = self._diagnostic_feature_range(col, rng)
                if value < mn or value > mx:
                    outliers[col] = {"value": float(value), "min": mn, "max": mx}
        if outliers:
            details["out_of_range"] = outliers

        return details

    def predict_battery_life(self, data: dict) -> float | None:
        """Compatibility wrapper for callers that only need the numeric value."""
        details = self.predict_battery_life_details(data)
        return details.get("prediction")


    # -------------------------------------------------------------------------
    # SECTION: BREAK-EVEN PIPELINE
    # -------------------------------------------------------------------------
    def _build_break_even_pipeline(self):
        """
        Pipeline:
          - RandomForestRegressor(propulsion power, pack voltage)
        """
        self.be_pipe = self._new_break_even_pipeline()

    @staticmethod
    def _new_break_even_pipeline():
        # Training uses measured steady-state motor power. Runtime prediction
        # places synchronized net array power into that same generic propulsion-
        # power feature to ask what steady speed the available power can sustain.
        return Pipeline([
            ('rf', RandomForestRegressor(
                n_estimators=100,
                min_samples_leaf=3,
                random_state=42
            ))
        ])


    def train_break_even_model(self, csv_path: str):
        """Serialize manual and automatic break-even training runs."""
        with self._training_lock:
            return self._train_break_even_model_unlocked(csv_path)

    def _train_break_even_model_unlocked(self, csv_path: str):
        """
        Train break-even model:
          features = [ 'BreakEven_Power_W', 'BP_PVS_Voltage' ]
          target   = observed speed during steady-state driving
        """
        df = pd.read_csv(csv_path)
        feats = self.BREAK_EVEN_FEATURES
        target = 'BreakEvenSpeed'

        missing = [c for c in feats + [target] if c not in df.columns]
        if missing:
            # Just warn, do not crash. Older training files may not have a
            # BreakEvenSpeed label until telemetry data is normalized/combined.
            self.log.warning(f"Skipping break-even training, missing required columns: {missing}")
            return

        for column in feats + [target]:
            df[column] = pd.to_numeric(df[column], errors='coerce')
        df = self._clean_data(df, feats + [target])
        if len(df) < self.MIN_BREAK_EVEN_TRAINING_ROWS:
            self.log.error(
                "Break-even training skipped: "
                f"{len(df)} valid steady-state rows; "
                f"need at least {self.MIN_BREAK_EVEN_TRAINING_ROWS}."
            )
            return False
        X = df[feats]
        y = df[target]

        # Evaluate chronologically so later telemetry is not leaked into the
        # validation window, then refit on every valid row for live use.
        split_index = max(1, min(len(df) - 1, int(len(df) * 0.8)))
        validation_pipe = self._new_break_even_pipeline()
        validation_pipe.fit(X.iloc[:split_index], y.iloc[:split_index])
        validation_predictions = validation_pipe.predict(X.iloc[split_index:])
        validation_target = y.iloc[split_index:]
        validation = {
            "rows": int(len(validation_target)),
            "mae_mph": float(mean_absolute_error(validation_target, validation_predictions)),
            "r2": (
                float(r2_score(validation_target, validation_predictions))
                if len(validation_target) >= 2
                else None
            ),
        }

        candidate_pipe = self._new_break_even_pipeline()
        candidate_pipe.fit(X, y)
        meta = {
            "feature_ranges": self._collect_feature_ranges(X, feats),
            "target_stats": self._target_stats(y),
            "trained_at": datetime.now(timezone.utc).isoformat(timespec='seconds'),
            "row_count": int(len(df)),
            "model_version": self.BREAK_EVEN_MODEL_VERSION,
            "features": list(feats),
            "label_definition": (
                "Observed vehicle speed while moving with absolute forward "
                f"acceleration <= {self.STEADY_STATE_MAX_ABS_FORWARD_G:.2f} g"
            ),
            "validation": validation,
        }
        joblib.dump({"pipeline": candidate_pipe, "meta": meta}, self.be_path)
        with self._model_lock:
            self.be_pipe = candidate_pipe
            self.be_meta.clear()
            self.be_meta.update(meta)
        self.log.info(f"Trained break-even model -> {self.be_path}")
        return True


    def predict_break_even_speed_details(self, data: dict) -> dict:
        """
        Predict break-even speed (mph) given:
          data['BreakEven_Power_W'], data['BP_PVS_Voltage']
        """
        feats = self.BREAK_EVEN_FEATURES
        details = {
            # Same structured response shape as battery-life predictions so one
            # diagnostics class can summarize both models consistently.
            "prediction": None,
            "uncertainty": None,
            "sigma": None,
            "missing_features": [],
            "invalid_features": [],
            "out_of_range": {},
        }

        missing = [k for k in feats if k not in data]
        if missing:
            self.log.error(f"Missing features for break-even: {missing}")
            details["missing_features"] = missing
            return details

        values = []
        invalid = []
        for k in feats:
            try:
                # Predictions are intentionally strict about numeric features;
                # bad strings become flags rather than guessed values.
                values.append(float(data[k]))
            except (TypeError, ValueError):
                invalid.append(k)
        if invalid:
            self.log.error(f"Invalid (non-numeric) features for break-even: {invalid}")
            details["invalid_features"] = invalid
            return details

        row = pd.DataFrame([values], columns=feats)
        try:
            with self._model_lock:
                pred, sigma = self._predict_with_uncertainty(self.be_pipe, row)
                ranges = dict(self.be_meta.get("feature_ranges", {}))
        except NotFittedError:
            self.log.warning("Break-even model not fitted yet, skipping prediction.")
            details["not_fitted"] = True
            return details
        except Exception as e:
            self.log.error(f"Error predicting break-even speed: {e}")
            details["error"] = str(e)
            return details

        details["prediction"] = pred
        details["sigma"] = sigma
        # Match the battery model's approximate 95% uncertainty convention.
        details["uncertainty"] = 1.96 * sigma if sigma is not None else None

        outliers = {}
        for col, value in row.iloc[0].items():
            # Runtime inputs outside the trained min/max range are worth
            # surfacing even when the forest still returns a number.
            rng = ranges.get(col)
            if rng:
                mn, mx = self._diagnostic_feature_range(col, rng)
                if value < mn or value > mx:
                    outliers[col] = {"value": float(value), "min": mn, "max": mx}
        if outliers:
            details["out_of_range"] = outliers

        return details

    def predict_break_even_speed(self, data: dict) -> float | None:
        """Compatibility wrapper for callers that only need the numeric value."""
        details = self.predict_break_even_speed_details(data)
        return details.get("prediction")


    def _predict_with_uncertainty(self, pipeline: Pipeline, X: pd.DataFrame) -> tuple[float, float]:
        """
        Run the pipeline while also deriving ensemble variance (1-sigma).
        """
        transformed = X
        for name, step in pipeline.steps[:-1]:
            # Apply every preprocessing step manually so we can inspect the
            # final forest's individual tree predictions below.
            transformed = step.transform(transformed)

        model = pipeline.steps[-1][1]
        # Preserve DataFrame for the forest itself (keeps feature names) but feed numpy
        # arrays to individual estimators to avoid "feature names" warnings.
        if hasattr(transformed, "to_numpy"):
            arr = transformed.to_numpy()
        else:
            arr = np.asarray(transformed)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)

        if not hasattr(model, "estimators_") or not getattr(model, "estimators_", None):
            # Non-ensemble fallback keeps this helper usable if a future model
            # type replaces RandomForestRegressor.
            pred = float(model.predict(transformed)[0])
            return pred, 0.0

        preds = np.array([estimator.predict(arr)[0] for estimator in model.estimators_], dtype=float)
        # Use the forest's normal prediction as the mean so behavior exactly
        # matches model.predict(), then report tree disagreement as sigma.
        mean = float(model.predict(transformed)[0])
        std = float(preds.std(ddof=1)) if preds.size > 1 else 0.0
        return mean, std


    # -------------------------------------------------------------------------
    # SECTION: COMBINING & RETRAINING
    # -------------------------------------------------------------------------
    def _normalize_training_frame(self, df: pd.DataFrame, source: str) -> pd.DataFrame:
        """
        Convert either a sparse training CSV or a full telemetry CSV into the
        exact numeric columns used by the saved model files.
        """
        normalized = df.copy()
        # Full telemetry exports teach the road-load curve only from steady
        # driving. Acceleration/braking power is not sustainable road load and
        # would bias the inferred break-even speed.
        if 'BreakEven_Power_W' not in normalized.columns:
            if 'Motors_Total_Bus_Power_W' in normalized.columns:
                normalized['BreakEven_Power_W'] = normalized['Motors_Total_Bus_Power_W']
            elif {
                'MC1BUS_Voltage',
                'MC1BUS_Current',
                'MC2BUS_Voltage',
                'MC2BUS_Current',
            }.issubset(normalized.columns):
                normalized['BreakEven_Power_W'] = (
                    pd.to_numeric(normalized['MC1BUS_Voltage'], errors='coerce')
                    * pd.to_numeric(normalized['MC1BUS_Current'], errors='coerce')
                    + pd.to_numeric(normalized['MC2BUS_Voltage'], errors='coerce')
                    * pd.to_numeric(normalized['MC2BUS_Current'], errors='coerce')
                )

        if 'BreakEvenSpeed' not in normalized.columns:
            normalized['BreakEvenSpeed'] = np.nan
            speed_column = next(
                (alias for alias in self.BREAK_EVEN_LABEL_ALIASES if alias in normalized.columns),
                None,
            )
            required = {'BreakEven_Power_W', 'IMU_FORWARD_G'}
            if speed_column and required.issubset(normalized.columns):
                speed = pd.to_numeric(normalized[speed_column], errors='coerce')
                motor_power = pd.to_numeric(
                    normalized['BreakEven_Power_W'], errors='coerce'
                )
                forward_g = pd.to_numeric(normalized['IMU_FORWARD_G'], errors='coerce')
                steady = (
                    (forward_g.abs() <= self.STEADY_STATE_MAX_ABS_FORWARD_G)
                    & (speed >= self.MIN_BREAK_EVEN_SPEED_MPH)
                    & (motor_power > 0.0)
                )
                if 'IMU_G_VALID' in normalized.columns:
                    imu_valid = pd.to_numeric(
                        normalized['IMU_G_VALID'], errors='coerce'
                    ) == 1
                    steady &= imu_valid
                normalized.loc[steady, 'BreakEvenSpeed'] = speed.loc[steady]
                self.log.info(
                    f"Derived {int(steady.sum())} steady-state road-load labels "
                    f"from {source}"
                )

        # Preserve rows usable by either model. Legacy sparse files will receive
        # an empty array-power column: their battery rows remain useful, while
        # old ordinary-speed labels cannot train the new break-even model.
        for col in self.TRAINING_COLUMNS:
            if col not in normalized.columns:
                normalized[col] = np.nan

        normalized = normalized[self.TRAINING_COLUMNS].copy()
        for col in self.TRAINING_COLUMNS:
            # Coerce instead of raising so one bad row does not throw away an
            # otherwise useful historical CSV.
            normalized[col] = pd.to_numeric(normalized[col], errors='coerce')

        before = len(normalized)
        normalized = normalized.replace([np.inf, -np.inf], np.nan)
        battery_required = [
            'BP_PVS_milliamp*s',
            'BP_PVS_Ah',
            'BP_PVS_Voltage',
            'Used_Ah_Remaining_Time',
        ]
        break_even_required = self.BREAK_EVEN_FEATURES + ['BreakEvenSpeed']
        usable = (
            normalized[battery_required].notna().all(axis=1)
            | normalized[break_even_required].notna().all(axis=1)
        )
        normalized = normalized.loc[usable].copy()
        dropped = before - len(normalized)
        if dropped:
            self.log.info(f"Dropped {dropped} incomplete/non-numeric training rows from {source}")

        return normalized


    def combine_and_retrain(self, old_file: str, new_files: list) -> str:
        """
        Merge current training data plus additional training or telemetry CSVs
        into combined_training_data.csv, retrain both models, promote the
        merged rows back into training_data.csv, and return the combined file
        path.
        """
        try:
            frames = []
            input_files = []
            if old_file:
                # Include the current training corpus first so imported files
                # extend rather than replace the user's existing data.
                input_files.append(old_file)
            input_files.extend(new_files or [])

            seen = set()
            for file_path in input_files:
                if not file_path:
                    continue
                file_path = os.path.abspath(file_path)
                if file_path in seen:
                    # Avoid double-counting if the user selects training_data.csv
                    # again in the file picker.
                    continue
                seen.add(file_path)

                if not os.path.exists(file_path):
                    self.log.warning(f"Skipping missing CSV: {file_path}")
                    continue

                try:
                    raw = pd.read_csv(file_path)
                except Exception as exc:
                    # Continue through the rest of the selected files; one bad
                    # export should not block the whole retrain attempt.
                    self.log.warning(f"Skipping unreadable CSV {file_path}: {exc}")
                    continue

                normalized = self._normalize_training_frame(raw, file_path)
                if normalized.empty:
                    self.log.warning(f"No usable training rows found in {file_path}")
                    continue
                self.log.info(f"Accepted {len(normalized)} training rows from {file_path}")
                frames.append(normalized)

            if not frames:
                self.log.error("No usable training rows found in selected CSV files.")
                return None

            combined = pd.concat(frames, ignore_index=True)
            # Duplicate rows are common when users import bundles more than
            # once. Drop exact duplicates after normalization.
            combined = combined.drop_duplicates(ignore_index=True)
            if combined.empty:
                self.log.error("Combined training data is empty after normalization.")
                return None

            out_dir = os.path.dirname(os.path.abspath(old_file)) if old_file else os.path.dirname(self.batt_path)
            os.makedirs(out_dir, exist_ok=True)
            out = os.path.join(out_dir, 'combined_training_data.csv')
            # Keep an audit file of the exact rows used for this combined run.
            combined.to_csv(out, index=False)
            self.log.info(f"Combined {len(combined)} usable training rows -> {out}")

            batt_ok = self.train_battery_life_model(out)
            be_ok = self.train_break_even_model(out)
            if not batt_ok or not be_ok:
                # Do not promote a merged corpus unless both model artifacts
                # were actually refreshed from it.
                return None

            if old_file:
                # Promotion makes training_data.csv the ongoing master corpus:
                # future live rows append to historical + imported data, and a
                # normal retrain later will use everything automatically.
                training_path = os.path.abspath(old_file)
                tmp_training_path = f"{training_path}.tmp"
                combined.to_csv(tmp_training_path, index=False)
                os.replace(tmp_training_path, training_path)
                self.log.info(f"Promoted combined training rows -> {training_path}")

            return out

        except Exception as e:
            self.log.error(f"Error combining/retraining: {e}")
            return None

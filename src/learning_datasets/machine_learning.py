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
from collections import deque
import joblib
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from sklearn import __version__ as sklearn_version
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
      - Battery life:   RF(saved feature schema) -> Used_Ah_Remaining_Time
      - Break-even:     RF([propulsion power, pack V]) -> sustainable speed
    """
    # The canonical sparse training schema. Full telemetry CSVs are normalized
    # down to exactly these columns before training model artifacts.
    TRAINING_COLUMNS = [
        'BP_PVS_milliamp*s',
        'BP_PVS_Ah',
        'BP_PVS_Voltage',
        'BP_ISH_Amps',
        'BP_ISH_SOC',
        'Shunt_Remaining_Ah',
        'Used_Ah_Remaining_Time',
        'Array_Estimated_Power_W',
        'BreakEven_Power_W',
        'BreakEvenSpeed',
        'BreakEven_Label_Weight',
        'Array_Estimate_Sample_1_W',
        'Array_Estimate_Sample_2_W',
        'Array_Estimate_Sample_3_W',
        'Array_Estimate_Sample_4_W',
        'Array_Estimate_Sample_5_W',
        'Array_Estimate_Window_Count',
        'Array_Estimate_Window_Spread_W',
        'Array_Estimate_Window_StdDev_W',
        'Array_Estimate_Frames_Total',
        'Array_Estimate_Frames_Usable',
        'Array_Estimate_Frames_Rejected',
        'Array_Estimate_Frame_Usable_Pct',
        'Array_Estimate_Published_Count',
        'Array_Estimate_Unavailable_Count',
        'Array_Estimate_Availability_Pct',
        'Array_Estimate_Missing_Telemetry_Count',
        'Array_Estimate_Voltage_Mismatch_Count',
        'Array_Estimate_Negative_Window_Count',
    ]
    # Full telemetry exports may not have BreakEvenSpeed yet. These fields are
    # accepted, in priority order, as the current speed label for that target.
    BREAK_EVEN_LABEL_ALIASES = [
        'MC1VEL_Speed',
        'MC2VEL_Speed',
        'NAV_VEHICLE_MPH',
        'NAV_GPS_MPH',
        'NAV_IMU_MPH',
    ]
    LEGACY_COLUMN_ALIASES = {
        # Older telemetry exports used a slash in this integrated-current field
        # name. The values are still milliamp-seconds, not a current-per-second
        # measurement, so map the spelling without changing the value.
        'BP_PVS_milliamp*s': (
            'BP_PVS_milliamp/s',
            'BP_PVS_milliamp_s',
        ),
        # Very old exports may only carry the shunt-derived remaining-time
        # target. It is compatible after the same finite/range checks.
        'Used_Ah_Remaining_Time': (
            'Shunt_Remaining_Time',
        ),
    }
    # A narrow training run may never observe the lower end of the vehicle's
    # normal pack-voltage range. Do not report PVS voltage extrapolation until
    # it falls below this known operational floor.
    PVS_VOLTAGE_QUALITY_MIN = 100.0
    BATTERY_BASE_FEATURES = [
        'BP_PVS_milliamp*s',
        'BP_PVS_Ah',
        'BP_PVS_Voltage',
    ]
    BATTERY_ENHANCED_FEATURES = BATTERY_BASE_FEATURES + [
        'BP_ISH_Amps',
        'BP_ISH_SOC',
        'Shunt_Remaining_Ah',
    ]
    BATTERY_MODEL_VERSION = 2
    MIN_BATTERY_TRAINING_ROWS = 20
    MIN_ENHANCED_BATTERY_TRAINING_ROWS = 50
    BATTERY_MIN_DISCHARGE_CURRENT_A = 0.5
    BREAK_EVEN_FEATURES = ['BreakEven_Power_W', 'BP_PVS_Voltage']
    BREAK_EVEN_MODEL_VERSION = 3
    MIN_BREAK_EVEN_TRAINING_ROWS = 20
    MIN_BREAK_EVEN_SPEED_MPH = 5.0
    STEADY_STATE_MAX_ABS_FORWARD_G = 0.03
    LEGACY_STEADY_MAX_SPEED_CHANGE_MPH = 1.0
    LEGACY_MAX_CONTROLLER_SPEED_DIFFERENCE_MPH = 2.0
    LEGACY_MIN_PROPULSION_POWER_W = 50.0
    LEGACY_MIN_SAMPLE_INTERVAL_SECONDS = 0.25
    LEGACY_MAX_SAMPLE_INTERVAL_SECONDS = 60.0
    LEGACY_LABEL_WEIGHT = 0.5
    MODERN_LABEL_WEIGHT = 1.0
    BATTERY_TARGET_MIN_HOURS = 0.0
    BATTERY_TARGET_MAX_HOURS = 24.0

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
        self._battery_runtime_history = deque(maxlen=5)
        self._battery_runtime_feature_schema = None

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
          - smooth the selected battery feature schema
          - RandomForestRegressor
        """
        self.batt_pipe = self._new_battery_pipeline(
            self.BATTERY_BASE_FEATURES
        )

    @staticmethod
    def _new_battery_pipeline(features):
        return Pipeline([
            ('smooth', MovingAverage(window=5, cols=list(features))),
            ('rf', RandomForestRegressor(
                # A modest forest keeps retraining responsive from the GUI while
                # still giving enough trees for a useful ensemble spread.
                n_estimators=100,
                min_samples_leaf=5,
                random_state=42
            )),
        ])

    def battery_model_features(self) -> list[str]:
        """Return the exact feature schema expected by the loaded battery PKL."""
        configured = self.batt_meta.get("features")
        configured_features = (
            [str(feature) for feature in configured]
            if isinstance(configured, (list, tuple)) and configured
            else []
        )

        try:
            model = self.batt_pipe.steps[-1][1]
            learned = getattr(model, "feature_names_in_", None)
            if learned is not None and len(learned):
                learned_features = [str(feature) for feature in learned]
                if (
                    configured_features
                    and configured_features != learned_features
                ):
                    self.log.warning(
                        "Battery model metadata features do not match the "
                        "fitted estimator; using the estimator schema."
                    )
                return learned_features
        except Exception:
            pass

        if configured_features:
            return configured_features

        try:
            smoother = self.batt_pipe.named_steps.get("smooth")
            columns = getattr(smoother, "cols", None)
            if columns:
                return [str(feature) for feature in columns]
        except Exception:
            pass
        return list(self.BATTERY_BASE_FEATURES)


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
        """Serialize manual and automatic battery model training runs."""
        with self._training_lock:
            return self._train_battery_life_model_unlocked(csv_path)

    def _train_battery_life_model_unlocked(self, csv_path: str):
        """
        Train a legacy-compatible three-input model, then automatically upgrade
        to current/SOC/capacity inputs once enough complete race rows exist.
        """
        raw = pd.read_csv(csv_path, low_memory=False)
        df = self._normalize_training_frame(raw, csv_path)
        target = 'Used_Ah_Remaining_Time'

        missing = [
            column
            for column in self.BATTERY_BASE_FEATURES + [target]
            if column not in df.columns
        ]
        if missing:
            self.log.error(f"Battery-life CSV missing columns: {missing}")
            return False

        battery_columns = list(dict.fromkeys(
            self.BATTERY_ENHANCED_FEATURES + [target]
        ))
        for column in battery_columns:
            if column not in df.columns:
                df[column] = np.nan
            df[column] = pd.to_numeric(df[column], errors='coerce')

        base_rows = self._clean_data(
            df,
            self.BATTERY_BASE_FEATURES + [target],
        )
        before_quality = len(base_rows)
        base_rows = base_rows.loc[
            (base_rows['BP_PVS_Voltage'] >= self.PVS_VOLTAGE_QUALITY_MIN)
            & (base_rows[target] > self.BATTERY_TARGET_MIN_HOURS)
            & (base_rows[target] <= self.BATTERY_TARGET_MAX_HOURS)
        ].copy()
        excluded_quality = before_quality - len(base_rows)
        if excluded_quality:
            self.log.info(
                "Excluded %s battery rows outside voltage/remaining-time "
                "training bounds from %s",
                excluded_quality,
                csv_path,
            )
        if len(base_rows) < self.MIN_BATTERY_TRAINING_ROWS:
            self.log.error(
                "Battery-life training skipped: "
                f"{len(base_rows)} valid rows; "
                f"need at least {self.MIN_BATTERY_TRAINING_ROWS}."
            )
            return False

        enhanced_rows = self._clean_data(
            base_rows,
            self.BATTERY_ENHANCED_FEATURES + [target],
        )
        enhanced_rows = enhanced_rows.loc[
            (
                enhanced_rows['BP_ISH_Amps']
                >= self.BATTERY_MIN_DISCHARGE_CURRENT_A
            )
            & enhanced_rows['BP_ISH_SOC'].between(0.0, 100.0)
            & (enhanced_rows['Shunt_Remaining_Ah'] > 0.0)
        ].copy()

        if len(enhanced_rows) >= self.MIN_ENHANCED_BATTERY_TRAINING_ROWS:
            training_rows = enhanced_rows
            feats = list(self.BATTERY_ENHANCED_FEATURES)
            schema = "enhanced-current-soc-capacity"
        else:
            training_rows = base_rows
            feats = list(self.BATTERY_BASE_FEATURES)
            schema = "legacy-compatible"

        X = training_rows[feats]
        y = training_rows[target]
        candidate_pipe = self._new_battery_pipeline(feats)
        candidate_pipe.fit(X, y)
        meta = {
            "feature_ranges": self._collect_feature_ranges(X, feats),
            "target_stats": self._target_stats(y),
            "trained_at": datetime.now(timezone.utc).isoformat(
                timespec='seconds'
            ),
            "row_count": int(len(training_rows)),
            "base_valid_row_count": int(len(base_rows)),
            "enhanced_valid_row_count": int(len(enhanced_rows)),
            "source": os.path.abspath(csv_path),
            "model_version": self.BATTERY_MODEL_VERSION,
            "sklearn_version": sklearn_version,
            "features": list(feats),
            "feature_schema": schema,
            "training_bounds": {
                "minimum_voltage": self.PVS_VOLTAGE_QUALITY_MIN,
                "minimum_discharge_current_a": (
                    self.BATTERY_MIN_DISCHARGE_CURRENT_A
                ),
                "remaining_time_hours": [
                    self.BATTERY_TARGET_MIN_HOURS,
                    self.BATTERY_TARGET_MAX_HOURS,
                ],
            },
        }

        temp_path = f"{self.batt_path}.tmp"
        joblib.dump({"pipeline": candidate_pipe, "meta": meta}, temp_path)
        os.replace(temp_path, self.batt_path)
        with self._model_lock:
            self.batt_pipe = candidate_pipe
            self.batt_meta.clear()
            self.batt_meta.update(meta)
            self._battery_runtime_history.clear()
            self._battery_runtime_feature_schema = tuple(feats)
        self.log.info(
            "Trained battery-life model (%s, %s rows) -> %s",
            schema,
            len(training_rows),
            self.batt_path,
        )
        return True


    def predict_battery_life_details(self, data: dict) -> dict:
        """
        Predict remaining time from the exact named features saved in the PKL.

        Legacy artifacts use three PVS values. Current artifacts may additionally
        use shunt current, SOC, and remaining capacity.
        """
        feats = self.battery_model_features()
        details = {
            # Keep the prediction response structured. TelemetryApplication can
            # display a best effort value while QualityDiagnostics expands flags.
            "prediction": None,
            "uncertainty": None,
            "sigma": None,
            "missing_features": [],
            "invalid_features": [],
            "out_of_range": {},
            "model_features": list(feats),
            "model_version": self.batt_meta.get("model_version", 1),
            "training_rows": self.batt_meta.get("row_count"),
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
                value = float(data[k])
                if not np.isfinite(value):
                    raise ValueError("non-finite")
                values.append(value)
            except (TypeError, ValueError):
                invalid.append(k)
        if invalid:
            self.log.error(f"Invalid (non-numeric) features for battery-life: {invalid}")
            details["invalid_features"] = invalid
            return details

        raw_row = pd.DataFrame([values], columns=feats)
        try:
            with self._model_lock:
                schema = tuple(feats)
                if self._battery_runtime_feature_schema != schema:
                    self._battery_runtime_history.clear()
                    self._battery_runtime_feature_schema = schema
                self._battery_runtime_history.append(dict(zip(feats, values)))
                smoothed_values = [
                    float(np.mean([
                        sample[feature]
                        for sample in self._battery_runtime_history
                    ]))
                    for feature in feats
                ]
                prediction_row = pd.DataFrame(
                    [smoothed_values],
                    columns=feats,
                )
                pred, sigma = self._predict_with_uncertainty(
                    self.batt_pipe,
                    prediction_row,
                )
                ranges = dict(self.batt_meta.get("feature_ranges", {}))
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

        outliers = {}
        for col, value in raw_row.iloc[0].items():
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
        raw = pd.read_csv(csv_path, low_memory=False)
        df = self._normalize_training_frame(raw, csv_path)
        feats = self.BREAK_EVEN_FEATURES
        target = 'BreakEvenSpeed'
        weight_column = 'BreakEven_Label_Weight'

        missing = [
            c for c in feats + [target, weight_column]
            if c not in df.columns
        ]
        if missing:
            # Just warn, do not crash. Older training files may not have a
            # BreakEvenSpeed label until telemetry data is normalized/combined.
            self.log.warning(f"Skipping break-even training, missing required columns: {missing}")
            return

        for column in feats + [target, weight_column]:
            df[column] = pd.to_numeric(df[column], errors='coerce')
        df = self._clean_data(df, feats + [target, weight_column])
        df = df.loc[
            (df[target] >= self.MIN_BREAK_EVEN_SPEED_MPH)
            & (df[weight_column] > 0.0)
        ].copy()
        if len(df) < self.MIN_BREAK_EVEN_TRAINING_ROWS:
            self.log.error(
                "Break-even training skipped: "
                f"{len(df)} valid steady-state rows; "
                f"need at least {self.MIN_BREAK_EVEN_TRAINING_ROWS}."
            )
            return False
        X = df[feats]
        y = df[target]
        weights = df[weight_column].clip(
            lower=0.1, upper=self.MODERN_LABEL_WEIGHT
        )

        # Evaluate chronologically so later telemetry is not leaked into the
        # validation window, then refit on every valid row for live use.
        split_index = max(1, min(len(df) - 1, int(len(df) * 0.8)))
        validation_pipe = self._new_break_even_pipeline()
        validation_pipe.fit(
            X.iloc[:split_index],
            y.iloc[:split_index],
            rf__sample_weight=weights.iloc[:split_index],
        )
        validation_predictions = validation_pipe.predict(X.iloc[split_index:])
        validation_target = y.iloc[split_index:]
        validation_weights = weights.iloc[split_index:]
        validation = {
            "rows": int(len(validation_target)),
            "mae_mph": float(
                mean_absolute_error(
                    validation_target,
                    validation_predictions,
                    sample_weight=validation_weights,
                )
            ),
            "r2": (
                float(
                    r2_score(
                        validation_target,
                        validation_predictions,
                        sample_weight=validation_weights,
                    )
                )
                if len(validation_target) >= 2
                else None
            ),
        }

        candidate_pipe = self._new_break_even_pipeline()
        candidate_pipe.fit(X, y, rf__sample_weight=weights)
        legacy_rows = int(
            (weights < self.MODERN_LABEL_WEIGHT).sum()
        )
        modern_rows = int(
            (weights >= self.MODERN_LABEL_WEIGHT).sum()
        )
        meta = {
            "feature_ranges": self._collect_feature_ranges(X, feats),
            "target_stats": self._target_stats(y),
            "trained_at": datetime.now(timezone.utc).isoformat(timespec='seconds'),
            "row_count": int(len(df)),
            "effective_weight_sum": float(weights.sum()),
            "model_version": self.BREAK_EVEN_MODEL_VERSION,
            "features": list(feats),
            "label_definition": (
                "Observed steady vehicle speed at measured motor bus power. "
                "Modern rows use the IMU acceleration gate; legacy rows use "
                "adjacent speed, timestamp, and controller-agreement gates."
            ),
            "label_quality": {
                "modern_full_weight_rows": modern_rows,
                "legacy_half_weight_rows": legacy_rows,
                "legacy_weight": self.LEGACY_LABEL_WEIGHT,
            },
            "source": os.path.abspath(csv_path),
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
    def _apply_legacy_column_aliases(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Fill canonical training fields from known historical spellings."""
        normalized = frame.copy()
        for canonical, aliases in self.LEGACY_COLUMN_ALIASES.items():
            if canonical in normalized.columns:
                canonical_values = pd.to_numeric(
                    normalized[canonical], errors='coerce'
                )
            else:
                canonical_values = pd.Series(
                    np.nan, index=normalized.index, dtype=float
                )

            for alias in aliases:
                if alias not in normalized.columns:
                    continue
                alias_values = pd.to_numeric(normalized[alias], errors='coerce')
                newly_filled = canonical_values.isna() & alias_values.notna()
                if newly_filled.any():
                    canonical_values = canonical_values.where(
                        ~newly_filled, alias_values
                    )
                    self.log.info(
                        "Mapped %s legacy values from %s to %s",
                        int(newly_filled.sum()),
                        alias,
                        canonical,
                    )
            normalized[canonical] = canonical_values
        return normalized

    @staticmethod
    def _coalesce_numeric(
        existing: pd.Series | None,
        fallback: pd.Series | None,
        index,
    ) -> pd.Series:
        """Return numeric existing values with missing rows filled by fallback."""
        if existing is None:
            result = pd.Series(np.nan, index=index, dtype=float)
        else:
            result = pd.to_numeric(existing, errors='coerce')
        if fallback is None:
            return result
        fallback_numeric = pd.to_numeric(fallback, errors='coerce')
        return result.where(result.notna(), fallback_numeric)

    def _derive_motor_speed_mph(
        self, frame: pd.DataFrame
    ) -> tuple[pd.Series | None, pd.Series | None]:
        """Return the best historical speed label and controller disagreement."""
        mc1_speed = (
            pd.to_numeric(frame['MC1VEL_Speed'], errors='coerce')
            if 'MC1VEL_Speed' in frame.columns
            else None
        )
        mc2_speed = (
            pd.to_numeric(frame['MC2VEL_Speed'], errors='coerce')
            if 'MC2VEL_Speed' in frame.columns
            else None
        )
        if mc1_speed is not None or mc2_speed is not None:
            available = [
                series for series in (mc1_speed, mc2_speed) if series is not None
            ]
            speed = pd.concat(available, axis=1).mean(axis=1, skipna=True)
            disagreement = (
                (mc1_speed - mc2_speed).abs()
                if mc1_speed is not None and mc2_speed is not None
                else None
            )
            return speed, disagreement

        for alias in (
            'NAV_VEHICLE_MPH',
            'NAV_GPS_MPH',
            'NAV_IMU_MPH',
        ):
            if alias in frame.columns:
                return pd.to_numeric(frame[alias], errors='coerce'), None

        # Velocity fields are metres per second in historical exports. Convert
        # them instead of treating them as the mph label used by the model.
        velocities = []
        for alias in ('MC1VEL_Velocity', 'MC2VEL_Velocity'):
            if alias in frame.columns:
                velocities.append(
                    pd.to_numeric(frame[alias], errors='coerce') * 2.2369362921
                )
        if velocities:
            return pd.concat(velocities, axis=1).mean(axis=1, skipna=True), None
        return None, None

    def _legacy_steady_state_mask(
        self,
        frame: pd.DataFrame,
        speed_mph: pd.Series,
        motor_power_w: pd.Series,
        controller_disagreement_mph: pd.Series | None,
    ) -> pd.Series:
        """Conservatively identify steady rows when old data has no IMU."""
        previous_change = speed_mph.diff().abs()
        next_change = (speed_mph.shift(-1) - speed_mph).abs()
        steady = (
            (speed_mph >= self.MIN_BREAK_EVEN_SPEED_MPH)
            & (motor_power_w > self.LEGACY_MIN_PROPULSION_POWER_W)
            & (
                previous_change
                <= self.LEGACY_STEADY_MAX_SPEED_CHANGE_MPH
            )
            & (next_change <= self.LEGACY_STEADY_MAX_SPEED_CHANGE_MPH)
        )

        if controller_disagreement_mph is not None:
            steady &= (
                controller_disagreement_mph
                <= self.LEGACY_MAX_CONTROLLER_SPEED_DIFFERENCE_MPH
            )

        if 'BP_PVS_Voltage' in frame.columns:
            voltage = pd.to_numeric(frame['BP_PVS_Voltage'], errors='coerce')
            steady &= voltage >= self.PVS_VOLTAGE_QUALITY_MIN

        timestamp_column = next(
            (
                column
                for column in ('timestamp', 'Timestamp')
                if column in frame.columns
            ),
            None,
        )
        if timestamp_column:
            timestamps = pd.to_datetime(
                frame[timestamp_column], errors='coerce'
            )
            previous_interval = timestamps.diff().dt.total_seconds()
            next_interval = (
                timestamps.shift(-1) - timestamps
            ).dt.total_seconds()
            steady &= previous_interval.between(
                self.LEGACY_MIN_SAMPLE_INTERVAL_SECONDS,
                self.LEGACY_MAX_SAMPLE_INTERVAL_SECONDS,
            )
            steady &= next_interval.between(
                self.LEGACY_MIN_SAMPLE_INTERVAL_SECONDS,
                self.LEGACY_MAX_SAMPLE_INTERVAL_SECONDS,
            )
        else:
            self.log.warning(
                "Legacy break-even labels not derived because the source has "
                "no timestamp for sample-gap validation."
            )
            return pd.Series(False, index=frame.index, dtype=bool)
        return steady.fillna(False)

    def _normalize_training_frame(self, df: pd.DataFrame, source: str) -> pd.DataFrame:
        """
        Convert either a sparse training CSV or a full telemetry CSV into the
        exact numeric columns used by the saved model files.
        """
        normalized = self._apply_legacy_column_aliases(df)
        original_power = (
            pd.to_numeric(normalized['BreakEven_Power_W'], errors='coerce')
            if 'BreakEven_Power_W' in normalized.columns
            else pd.Series(np.nan, index=normalized.index, dtype=float)
        )

        # Full telemetry exports teach the road-load curve only from steady
        # driving. Acceleration/braking power is not sustainable road load and
        # would bias the inferred break-even speed.
        derived_power = None
        if 'Motors_Total_Bus_Power_W' in normalized.columns:
            derived_power = pd.to_numeric(
                normalized['Motors_Total_Bus_Power_W'], errors='coerce'
            )
        if {
            'MC1BUS_Voltage',
            'MC1BUS_Current',
            'MC2BUS_Voltage',
            'MC2BUS_Current',
        }.issubset(normalized.columns):
            bus_power = (
                pd.to_numeric(
                    normalized['MC1BUS_Voltage'], errors='coerce'
                )
                * pd.to_numeric(
                    normalized['MC1BUS_Current'], errors='coerce'
                )
                + pd.to_numeric(
                    normalized['MC2BUS_Voltage'], errors='coerce'
                )
                * pd.to_numeric(
                    normalized['MC2BUS_Current'], errors='coerce'
                )
            )
            derived_power = self._coalesce_numeric(
                derived_power, bus_power, normalized.index
            )
        normalized['BreakEven_Power_W'] = self._coalesce_numeric(
            original_power, derived_power, normalized.index
        )

        speed, controller_disagreement = self._derive_motor_speed_mph(normalized)
        if 'BreakEvenSpeed' in normalized.columns:
            labels = pd.to_numeric(
                normalized['BreakEvenSpeed'], errors='coerce'
            )
        else:
            labels = pd.Series(np.nan, index=normalized.index, dtype=float)
        if 'BreakEven_Label_Weight' in normalized.columns:
            label_weights = pd.to_numeric(
                normalized['BreakEven_Label_Weight'], errors='coerce'
            )
        else:
            label_weights = pd.Series(
                np.nan, index=normalized.index, dtype=float
            )

        # Existing labels are trusted only when the canonical power feature
        # already accompanied them. Otherwise an old ordinary-speed column
        # could silently become a false break-even label.
        trusted_existing = labels.notna() & original_power.notna()
        labels = labels.where(trusted_existing)
        label_weights = label_weights.where(trusted_existing)
        label_weights.loc[trusted_existing & label_weights.isna()] = (
            self.MODERN_LABEL_WEIGHT
        )

        if speed is not None:
            motor_power = pd.to_numeric(
                normalized['BreakEven_Power_W'], errors='coerce'
            )
            unlabeled = labels.isna()
            if 'IMU_FORWARD_G' in normalized.columns:
                forward_g = pd.to_numeric(
                    normalized['IMU_FORWARD_G'], errors='coerce'
                )
                modern_steady = (
                    unlabeled
                    & forward_g.notna()
                    & (
                        forward_g.abs()
                        <= self.STEADY_STATE_MAX_ABS_FORWARD_G
                    )
                    & (speed >= self.MIN_BREAK_EVEN_SPEED_MPH)
                    & (motor_power > 0.0)
                )
                if 'IMU_G_VALID' in normalized.columns:
                    imu_valid = pd.to_numeric(
                        normalized['IMU_G_VALID'], errors='coerce'
                    ) == 1
                    modern_steady &= imu_valid
                labels.loc[modern_steady] = speed.loc[modern_steady]
                label_weights.loc[modern_steady] = self.MODERN_LABEL_WEIGHT
                if modern_steady.any():
                    self.log.info(
                        "Derived %s IMU-gated steady-state road-load labels "
                        "from %s",
                        int(modern_steady.sum()),
                        source,
                    )
            else:
                forward_g = pd.Series(
                    np.nan, index=normalized.index, dtype=float
                )

            legacy_candidates = labels.isna() & forward_g.isna()
            legacy_steady = pd.Series(
                False, index=normalized.index, dtype=bool
            )
            if legacy_candidates.any():
                legacy_steady = self._legacy_steady_state_mask(
                    normalized,
                    speed,
                    motor_power,
                    controller_disagreement,
                )
                legacy_steady &= legacy_candidates
            labels.loc[legacy_steady] = speed.loc[legacy_steady]
            label_weights.loc[legacy_steady] = self.LEGACY_LABEL_WEIGHT
            if legacy_steady.any():
                self.log.info(
                    "Derived %s lower-weight legacy steady-state road-load "
                    "labels from %s",
                    int(legacy_steady.sum()),
                    source,
                )

        normalized['BreakEvenSpeed'] = labels
        normalized['BreakEven_Label_Weight'] = label_weights

        # Preserve rows usable by either model. Legacy sparse files will receive
        # empty array provenance: their battery rows remain useful, while raw
        # bus/speed rows can teach a lower-weight legacy road-load baseline.
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
        break_even_required = self.BREAK_EVEN_FEATURES + [
            'BreakEvenSpeed',
            'BreakEven_Label_Weight',
        ]
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
                    raw = pd.read_csv(file_path, low_memory=False)
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

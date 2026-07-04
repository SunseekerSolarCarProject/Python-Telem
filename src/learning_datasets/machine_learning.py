# src/machine_learning_model.py

"""
MachineLearningModel for solar‐car telemetry:
 1. Battery life prediction using integrated PV current
 2. Break-even speed prediction using integrated PV current
Both use RandomForestRegressor pipelines with moving‐average smoothing.
"""

import os
import logging
import joblib
import pandas as pd
import numpy as np
from datetime import datetime

from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.exceptions import NotFittedError
from sklearn.utils.validation import check_is_fitted
from sklearn.base import TransformerMixin, BaseEstimator


class MovingAverage(TransformerMixin, BaseEstimator):
    """
    Rolling‐average smoother over `window` rows for specified columns.
    """
    def __init__(self, window: int = 50, cols: list = None):
        self.window = window
        self.cols = cols or []

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        df = X.copy()
        for c in self.cols:
            df[c] = df[c].rolling(self.window, min_periods=1).mean()
        return df


class MachineLearningModel:
    """
    Encapsulates both:
      - Battery life:   RF([PV_Ah, PV_V]) -> Used_Ah_Remaining_Time
      - Break-even:     RF([PV_mA_s, PV_V])       -> BreakEvenSpeed
    """
    TRAINING_COLUMNS = [
        'BP_PVS_milliamp*s',
        'BP_PVS_Ah',
        'BP_PVS_Voltage',
        'Used_Ah_Remaining_Time',
        'BreakEvenSpeed',
    ]
    BREAK_EVEN_LABEL_ALIASES = [
        'MC1VEL_Speed',
        'MC1VEL_Velocity',
        'NAV_VEHICLE_MPH',
        'NAV_GPS_MPH',
        'NAV_IMU_MPH',
    ]

    def __init__(self, model_dir: str = None):
        # --- Logger ---
        self.log = logging.getLogger(self.__class__.__name__)
        self.log.setLevel(logging.INFO)

        # --- Model directory & paths ---
        base = os.path.dirname(os.path.abspath(__file__))
        if model_dir is None:
            # default back-compat: sibling "models" folder next to this file
            model_dir = os.path.join(base, 'models')
        os.makedirs(model_dir, exist_ok=True)

        self.batt_path = os.path.join(model_dir, 'battery_life_model.pkl')
        self.be_path   = os.path.join(model_dir, 'break_even_model.pkl')

        # --- Build pipelines ---
        self._build_battery_pipeline()
        self._build_break_even_pipeline()

        # --- Metadata holders for diagnostics ---
        self.batt_meta: dict = {}
        self.be_meta: dict = {}

        # --- Load or train on startup ---
        self._load_or_train(self.batt_pipe, self.batt_path, self.train_battery_life_model, self.batt_meta)
        self._load_or_train(self.be_pipe,   self.be_path,   self.train_break_even_model,   self.be_meta)


    def _load_model_bundle(self, obj):
        """
        Normalize joblib payloads so we can support legacy pipeline-only dumps
        as well as newer {pipeline, meta} bundles.
        """
        meta: dict = {}
        pipeline = obj
        if isinstance(obj, dict):
            pipeline = obj.get('pipeline') or obj.get('model') or obj.get('pipeline_') or obj
            meta = obj.get('meta') or {}
        return pipeline, meta


    def _load_or_train(self, pipe: Pipeline, path: str, train_fn, meta_target: dict):
        """
        If a fitted model exists at `path`, load it.
        Otherwise, retrain by calling `train_fn(...)` on training_data.csv.
        """
        if os.path.exists(path):
            try:
                loaded = joblib.load(path)
                pipeline, meta = self._load_model_bundle(loaded)
                check_is_fitted(pipeline)
                # replace pipeline steps in place
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
                train_fn(td)
                return
        self.log.warning(f"No training_data.csv found near {os.path.dirname(path)} to train model.")


    def _clean_data(self, df: pd.DataFrame, cols: list) -> pd.DataFrame:
        """
        Replace infinities with NaN and drop any rows lacking required columns.
        """
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
                n_estimators=100,
                min_samples_leaf=5,
                random_state=42
            )),
        ])


    def _collect_feature_ranges(self, df: pd.DataFrame, feats: list[str]) -> dict:
        ranges: dict[str, tuple[float, float]] = {}
        for col in feats:
            series = df[col]
            if series.empty:
                continue
            ranges[col] = (float(series.min()), float(series.max()))
        return ranges


    def _target_stats(self, y: pd.Series) -> dict:
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
            self.log.error(f"Battery-life CSV missing columns: {missing}")
            return

        df = self._clean_data(df, feats + [target])
        if df.empty:
            self.log.error("Battery-life training skipped: no valid numeric rows after cleaning.")
            return False
        X = df[feats]
        y = df[target]

        self.batt_pipe.fit(X, y)
        meta = {
            "feature_ranges": self._collect_feature_ranges(X, feats),
            "target_stats": self._target_stats(y),
            "trained_at": datetime.utcnow().isoformat(timespec='seconds') + "Z",
        }
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
        details["uncertainty"] = 1.96 * sigma if sigma is not None else None

        ranges = self.batt_meta.get("feature_ranges", {}) if isinstance(self.batt_meta, dict) else {}
        outliers = {}
        for col, value in row.iloc[0].items():
            rng = ranges.get(col)
            if rng:
                mn, mx = rng
                if value < mn or value > mx:
                    outliers[col] = {"value": float(value), "min": mn, "max": mx}
        if outliers:
            details["out_of_range"] = outliers

        return details

    def predict_battery_life(self, data: dict) -> float | None:
        details = self.predict_battery_life_details(data)
        return details.get("prediction")


    # -------------------------------------------------------------------------
    # SECTION: BREAK-EVEN PIPELINE
    # -------------------------------------------------------------------------
    def _build_break_even_pipeline(self):
        """
        Pipeline:
          - smooth PV_mA_s, PV_V
          - RandomForestRegressor
        """
        self.be_pipe = Pipeline([
            ('smooth', MovingAverage(window=5, cols=[
                'BP_PVS_milliamp*s',
                'BP_PVS_Voltage'
            ])),
            ('rf', RandomForestRegressor(
                n_estimators=100,
                min_samples_leaf=5,
                random_state=42
            ))
        ])


    def train_break_even_model(self, csv_path: str):
        """
        Train break-even model:
          features = [ 'BP_PVS_milliamp*s', 'BP_PVS_Voltage' ]
          target   =   'BreakEvenSpeed'
        """
        df = pd.read_csv(csv_path)
        feats  = ['BP_PVS_milliamp*s', 'BP_PVS_Voltage']
        target = 'BreakEvenSpeed'

        missing = [c for c in feats + [target] if c not in df.columns]
        if missing:
            # just warn, don’t crash — we’ll train later once you have labels
            self.log.warning(f"Skipping break-even training, missing required columns: {missing}")
            return

        df = self._clean_data(df, feats + [target])
        if df.empty:
            self.log.error("Break-even training skipped: no valid numeric rows after cleaning.")
            return False
        X = df[feats]
        y = df[target]

        self.be_pipe.fit(X, y)
        meta = {
            "feature_ranges": self._collect_feature_ranges(X, feats),
            "target_stats": self._target_stats(y),
            "trained_at": datetime.utcnow().isoformat(timespec='seconds') + "Z",
        }
        joblib.dump({"pipeline": self.be_pipe, "meta": meta}, self.be_path)
        self.be_meta.clear()
        self.be_meta.update(meta)
        self.log.info(f"Trained break-even model -> {self.be_path}")
        return True


    def predict_break_even_speed_details(self, data: dict) -> dict:
        """
        Predict break-even speed (mph) given:
          data['BP_PVS_milliamp*s'], data['BP_PVS_Voltage']
        """
        feats = ['BP_PVS_milliamp*s', 'BP_PVS_Voltage']
        details = {
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
                values.append(float(data[k]))
            except (TypeError, ValueError):
                invalid.append(k)
        if invalid:
            self.log.error(f"Invalid (non-numeric) features for break-even: {invalid}")
            details["invalid_features"] = invalid
            return details

        row = pd.DataFrame([values], columns=feats)
        try:
            pred, sigma = self._predict_with_uncertainty(self.be_pipe, row)
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
        details["uncertainty"] = 1.96 * sigma if sigma is not None else None

        ranges = self.be_meta.get("feature_ranges", {}) if isinstance(self.be_meta, dict) else {}
        outliers = {}
        for col, value in row.iloc[0].items():
            rng = ranges.get(col)
            if rng:
                mn, mx = rng
                if value < mn or value > mx:
                    outliers[col] = {"value": float(value), "min": mn, "max": mx}
        if outliers:
            details["out_of_range"] = outliers

        return details

    def predict_break_even_speed(self, data: dict) -> float | None:
        details = self.predict_break_even_speed_details(data)
        return details.get("prediction")


    def _predict_with_uncertainty(self, pipeline: Pipeline, X: pd.DataFrame) -> tuple[float, float]:
        """
        Run the pipeline while also deriving ensemble variance (1-sigma).
        """
        transformed = X
        for name, step in pipeline.steps[:-1]:
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
            pred = float(model.predict(transformed)[0])
            return pred, 0.0

        preds = np.array([estimator.predict(arr)[0] for estimator in model.estimators_], dtype=float)
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
        if 'BreakEvenSpeed' not in normalized.columns:
            for alias in self.BREAK_EVEN_LABEL_ALIASES:
                if alias in normalized.columns:
                    normalized['BreakEvenSpeed'] = normalized[alias]
                    self.log.info(f"Using {alias} as BreakEvenSpeed label for {source}")
                    break

        missing = [col for col in self.TRAINING_COLUMNS if col not in normalized.columns]
        if missing:
            self.log.warning(f"Skipping {source}; missing training columns: {missing}")
            return pd.DataFrame(columns=self.TRAINING_COLUMNS)

        normalized = normalized[self.TRAINING_COLUMNS].copy()
        for col in self.TRAINING_COLUMNS:
            normalized[col] = pd.to_numeric(normalized[col], errors='coerce')

        before = len(normalized)
        normalized = normalized.replace([np.inf, -np.inf], np.nan).dropna(subset=self.TRAINING_COLUMNS)
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
                input_files.append(old_file)
            input_files.extend(new_files or [])

            seen = set()
            for file_path in input_files:
                if not file_path:
                    continue
                file_path = os.path.abspath(file_path)
                if file_path in seen:
                    continue
                seen.add(file_path)

                if not os.path.exists(file_path):
                    self.log.warning(f"Skipping missing CSV: {file_path}")
                    continue

                try:
                    raw = pd.read_csv(file_path)
                except Exception as exc:
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
            combined = combined.drop_duplicates(ignore_index=True)
            if combined.empty:
                self.log.error("Combined training data is empty after normalization.")
                return None

            out_dir = os.path.dirname(os.path.abspath(old_file)) if old_file else os.path.dirname(self.batt_path)
            os.makedirs(out_dir, exist_ok=True)
            out = os.path.join(out_dir, 'combined_training_data.csv')
            combined.to_csv(out, index=False)
            self.log.info(f"Combined {len(combined)} usable training rows -> {out}")

            batt_ok = self.train_battery_life_model(out)
            be_ok = self.train_break_even_model(out)
            if not batt_ok or not be_ok:
                return None

            if old_file:
                training_path = os.path.abspath(old_file)
                tmp_training_path = f"{training_path}.tmp"
                combined.to_csv(tmp_training_path, index=False)
                os.replace(tmp_training_path, training_path)
                self.log.info(f"Promoted combined training rows -> {training_path}")

            return out

        except Exception as e:
            self.log.error(f"Error combining/retraining: {e}")
            return None

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

from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.exceptions import NotFittedError
from sklearn.utils.validation import check_is_fitted
from sklearn.base import TransformerMixin, BaseEstimator


class MovingAverage(TransformerMixin, BaseEstimator):
    """
    Rolling‐average smoother over `window` rows for specified columns.
    """
    def __init__(self, window: int = 5, cols: list = None):
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

    def __init__(self, model_dir: str = None):
        # --- Logger ---
        self.log = logging.getLogger(self.__class__.__name__)
        self.log.setLevel(logging.INFO)

        # --- Model directory & paths ---
        base = os.path.dirname(os.path.abspath(__file__))
        if model_dir is None:
            model_dir = os.path.join(base, 'models')
        os.makedirs(model_dir, exist_ok=True)

        self.batt_path = os.path.join(model_dir, 'battery_life_model.pkl')
        self.be_path   = os.path.join(model_dir, 'break_even_model.pkl')

        # --- Build pipelines ---
        self._build_battery_pipeline()
        self._build_break_even_pipeline()

        # --- Load or train on startup ---
        self._load_or_train(self.batt_pipe, self.batt_path, self.train_battery_life_model)
        self._load_or_train(self.be_pipe,   self.be_path,   self.train_break_even_model)


    def _load_or_train(self, pipe: Pipeline, path: str, train_fn):
        """
        If a fitted model exists at `path`, load it.
        Otherwise, retrain by calling `train_fn(...)` on training_data.csv.
        """
        if os.path.exists(path):
            try:
                m = joblib.load(path)
                check_is_fitted(m)
                # replace pipeline steps in place
                pipe.steps[:] = m.steps
                self.log.info(f"Loaded fitted model from {path}")
                return
            except Exception:
                self.log.warning(f"Could not load fitted model at {path}; retraining.")
        # retrain if CSV available
        td = os.path.join(os.path.dirname(path), '..', 'application_data', 'training_data.csv')
        if os.path.exists(td) and os.path.getsize(td) > 0:
            train_fn(td)
        else:
            self.log.warning(f"No training_data.csv at {td} to train model.")


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
                'BP_PVS_milliamp/s',
                'BP_PVS_Ah',
                'BP_PVS_Voltage'
            ])),
            ('rf', RandomForestRegressor(
                n_estimators=100,
                min_samples_leaf=5,
                random_state=42
            )),
        ])


    def train_battery_life_model(self, csv_path: str):
        """
        Train battery-life model:
          features = [ 'BP_PVS_milliamp/s', 'BP_PVS_Ah', 'BP_PVS_Voltage' ]
          target   =   'Used_Ah_Remaining_Time'
        """
        df = pd.read_csv(csv_path)
        feats  = ['BP_PVS_milliamp/s', 'BP_PVS_Ah', 'BP_PVS_Voltage']
        target = 'Used_Ah_Remaining_Time'

        missing = [c for c in feats + [target] if c not in df.columns]
        if missing:
            self.log.error(f"Battery-life CSV missing columns: {missing}")
            return

        df = self._clean_data(df, feats + [target])
        X = df[feats]
        y = df[target]

        self.batt_pipe.fit(X, y)
        joblib.dump(self.batt_pipe, self.batt_path)
        self.log.info(f"Trained battery-life model -> {self.batt_path}")


    def predict_battery_life(self, data: dict) -> float:
        """
        Predict remaining time (hours) given:
          data['BP_PVS_milliamp/s'],
          data['BP_PVS_Ah'],
          data['BP_PVS_Voltage']
        """
        from sklearn.exceptions import NotFittedError

        feats = ['BP_PVS_milliamp/s', 'BP_PVS_Ah', 'BP_PVS_Voltage']
        if any(k not in data for k in feats):
            self.log.error(f"Missing features for battery-life: {feats}")
            return None

        row = pd.DataFrame([[data[k] for k in feats]], columns=feats)
        try:
            return float(self.batt_pipe.predict(row)[0])
        except NotFittedError:
            self.log.warning("Battery-life model not fitted yet, skipping prediction.")
            return None
        except Exception as e:
            self.log.error(f"Error predicting battery-life: {e}")
            return None


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
                'BP_PVS_milliamp/s',
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
          features = [ 'BP_PVS_milliamp/s', 'BP_PVS_Voltage' ]
          target   =   'BreakEvenSpeed'
        """
        df = pd.read_csv(csv_path)
        feats  = ['BP_PVS_milliamp/s', 'BP_PVS_Voltage']
        target = 'BreakEvenSpeed'

        missing = [c for c in feats + [target] if c not in df.columns]
        if missing:
            # just warn, don’t crash — we’ll train later once you have labels
            self.log.warning(f"Skipping break-even training, missing required columns: {missing}")
            return

        df = self._clean_data(df, feats + [target])
        X = df[feats]
        y = df[target]

        self.be_pipe.fit(X, y)
        joblib.dump(self.be_pipe, self.be_path)
        self.log.info(f"Trained break-even model → {self.be_path}")


    def predict_break_even_speed(self, data: dict) -> float:
        """
        Predict break-even speed (mph) given:
          data['BP_PVS_milliamp/s'], data['BP_PVS_Voltage']
        """
        from sklearn.exceptions import NotFittedError

        feats = ['BP_PVS_milliamp/s', 'BP_PVS_Voltage']
        if any(k not in data for k in feats):
            self.log.error(f"Missing features for break-even: {feats}")
            return None

        row = pd.DataFrame([[data[k] for k in feats]], columns=feats)
        try:
            return float(self.be_pipe.predict(row)[0])
        except NotFittedError:
            self.log.warning("Break-even model not fitted yet, skipping prediction.")
            return None
        except Exception as e:
            self.log.error(f"Error predicting break-even speed: {e}")
            return None


    # -------------------------------------------------------------------------
    # SECTION: COMBINING & RETRAINING
    # -------------------------------------------------------------------------
    def combine_and_retrain(self, old_file: str, new_files: list) -> str:
        """
        Merge old + new CSVs into combined_training_data.csv,
        retrain both models, return the combined file path.
        """
        try:
            if not os.path.exists(old_file):
                self.log.error(f"Old data missing: {old_file}")
                return None

            combined = pd.read_csv(old_file)
            for f in new_files:
                if os.path.exists(f):
                    combined = pd.concat([combined, pd.read_csv(f)], ignore_index=True)
                else:
                    self.log.warning(f"Skipping missing: {f}")

            out = 'combined_training_data.csv'
            combined.to_csv(out, index=False)
            self.log.info(f"Combined data → {out}")

            self.train_battery_life_model(out)
            self.train_break_even_model(out)
            return out

        except Exception as e:
            self.log.error(f"Error combining/retraining: {e}")
            return None

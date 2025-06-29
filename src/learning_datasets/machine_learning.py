"""
src/machine_learning_model.py

Defines MachineLearningModel for:
 1. Battery life prediction  (Linear regression from current, voltage, Ah to remaining time)
 2. Net-current model        (Linear regression from speed, PV current to battery draw)
 3. Break-even speed         (Analytic solution where net-current = 0)

Includes loading, cleaning, training, saving, and predicting with robust checks.
"""
import os
import logging
import threading
import joblib
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.exceptions import NotFittedError
from sklearn.utils.validation import check_is_fitted


class MachineLearningModel:
    """
    Encapsulates ML workflows for:
      - Battery life prediction
      - Net-current estimation
      - Break-even speed calculation
    """

    def __init__(
        self,
        model_dir: str = None,
        battery_life_file: str = 'battery_life_model.pkl',
        net_current_file: str = 'net_current_model.pkl'
    ):
        # --- Logger setup ---
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)

        # --- Determine & create model directory ---
        if model_dir is None:
            base = os.path.dirname(os.path.abspath(__file__))
            model_dir = os.path.join(base, 'models')
        os.makedirs(model_dir, exist_ok=True)

        # --- File paths for saved models ---
        self.battery_life_path = os.path.join(model_dir, battery_life_file)
        self.net_current_path = os.path.join(model_dir, net_current_file)

        # --- In-memory placeholders ---
        self.battery_life_model = None
        self.net_current_model = None
        self.break_even_model = None  # alias for net_current_model

        # --- Load existing models (if fitted) ---
        self._load_model(self.battery_life_path, 'battery_life_model', 'Battery life')
        self._load_model(self.net_current_path, 'net_current_model', 'Net-current')
        # Ensure break-even alias
        self.break_even_model = self.net_current_model

    # -------------------------------------------------------------------------
    # SECTION: MODEL LOADING
    # -------------------------------------------------------------------------
    def _load_model(self, path: str, attr: str, desc: str):
        """
        Generic loader: if model file exists and is fitted, assign it;
        otherwise clear so retraining is forced.
        """
        if not os.path.exists(path):
            self.logger.info(f"No existing {desc} model at {path}.")
            return
        try:
            model = joblib.load(path)
            check_is_fitted(model, attributes=['coef_', 'n_features_in_'])
            setattr(self, attr, model)
            self.logger.info(f"Loaded {desc} model from {path}.")
        except (NotFittedError, AttributeError):
            self.logger.warning(f"Loaded {desc} model is not fitted—will retrain.")
            setattr(self, attr, None)
        except Exception as e:
            self.logger.error(f"Error loading {desc} model: {e}")
            setattr(self, attr, None)

    # -------------------------------------------------------------------------
    # SECTION: DATA CLEANING UTILITIES
    # -------------------------------------------------------------------------
    def _clean_data(self, df: pd.DataFrame, cols: list) -> pd.DataFrame:
        """
        Replace infinities with NaN and drop rows missing any required columns.
        """
        df = df.replace([np.inf, -np.inf], np.nan)
        return df.dropna(subset=cols)

    # -------------------------------------------------------------------------
    # SECTION: BATTERY LIFE MODEL
    # -------------------------------------------------------------------------
    def train_battery_life_model(self, data_file: str):
        """
        Train battery life: predicts Used_Ah_Remaining_Time
        from [BP_ISH_Amps, BP_PVS_Voltage, BP_PVS_Ah]
        """
        required = ['BP_ISH_Amps', 'BP_PVS_Voltage', 'BP_PVS_Ah', 'Used_Ah_Remaining_Time']
        self._train_generic(
            data_file=data_file,
            required=required,
            features=required[:-1],
            target=required[-1],
            attr='battery_life_model',
            save_path=self.battery_life_path,
            desc='Battery life'
        )

    def predict_battery_life(self, input_data: dict) -> float:
        """
        Predict remaining time given input measurements.
        """
        return self._predict_generic(
            input_data=input_data,
            attr='battery_life_model',
            required=['BP_ISH_Amps', 'BP_PVS_Voltage', 'BP_PVS_Ah'],
            desc='Battery life'
        )

    # -------------------------------------------------------------------------
    # SECTION: BREAK-EVEN MODEL ALIAS
    # -------------------------------------------------------------------------
    def train_break_even_model(self, data_file: str):
        """
        Alias for backward compatibility: trains net-current model
        as the break-even predictor.
        """
        self.train_net_current_model(data_file)

    # -------------------------------------------------------------------------
    # SECTION: NET-CURRENT MODEL
    # -------------------------------------------------------------------------
    def train_net_current_model(self, data_file: str):
        """
        Train net-current model: predicts BP_ISH_Amps
        from [MC1VEL_Speed, BP_PVS_milliamp/s]
        """
        required = ['MC1VEL_Speed', 'BP_PVS_milliamp/s', 'BP_ISH_Amps']
        self._train_generic(
            data_file=data_file,
            required=required,
            features=required[:-1],
            target=required[-1],
            attr='net_current_model',
            save_path=self.net_current_path,
            desc='Net-current'
        )
        # Update break-even alias
        self.break_even_model = self.net_current_model

    # -------------------------------------------------------------------------
    # SECTION: GENERIC TRAINING ROUTINE
    # -------------------------------------------------------------------------
    def _train_generic(
        self,
        data_file: str,
        required: list,
        features: list,
        target: str,
        attr: str,
        save_path: str,
        desc: str
    ):
        """
        Generic: read CSV, clean, split, fit LinearRegression, save, and log R².
        """
        if not os.path.exists(data_file):
            self.logger.error(f"Training file not found: {data_file}")
            return
        try:
            df = pd.read_csv(data_file)
            missing = [c for c in required if c not in df.columns]
            if missing:
                self.logger.error(f"{desc} missing cols: {missing}")
                return
            df = self._clean_data(df, required)
            self.logger.info(f"{desc}: {len(df)} rows after cleaning.")

            X = df[features]
            y = df[target]

            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
            model = LinearRegression().fit(X_train, y_train)

            joblib.dump(model, save_path)
            setattr(self, attr, model)
            self.logger.info(f"{desc} model trained and saved to {save_path}.")

            score = model.score(X_test, y_test)
            self.logger.info(f"{desc} R² = {score:.4f}")
        except Exception as e:
            self.logger.error(f"Error training {desc}: {e}")

    # -------------------------------------------------------------------------
    # SECTION: BREAK-EVEN SPEED CALCULATION
    # -------------------------------------------------------------------------
    def predict_break_even_speed(self, input_data: dict) -> float:
        """
        Solve net-current = 0 using coefficients:
          I_net = a*v + b*I_PV + c  =>  v_be = -(b*I_PV + c)/a
        """
        model = self.net_current_model
        if model is None or not hasattr(model, 'coef_'):
            self.logger.warning("Net-current model unavailable.")
            return None
        try:
            check_is_fitted(model)
        except NotFittedError:
            self.logger.warning("Net-current model not fitted.")
            return None

        pv_key = 'BP_PVS_milliamp/s'
        if pv_key not in input_data:
            self.logger.error(f"Missing PV current key: {pv_key}")
            return None

        Ipv = input_data[pv_key]
        a, b = model.coef_
        c = model.intercept_
        try:
            return - (b * Ipv + c) / a
        except ZeroDivisionError:
            self.logger.error("Speed coefficient zero—cannot solve.")
            return None
        except Exception as e:
            self.logger.error(f"Error computing break-even: {e}")
            return None

    # -------------------------------------------------------------------------
    # SECTION: GENERIC PREDICTION ROUTINE
    # -------------------------------------------------------------------------
    def _predict_generic(self, input_data, attr: str, required: list, desc: str):
        """
        Generic: ensure model fitted, check required features, predict.
        """
        model = getattr(self, attr)
        if model is None or not hasattr(model, 'coef_'):
            self.logger.warning(f"{desc} model unavailable.")
            return None
        try:
            check_is_fitted(model)
        except NotFittedError:
            self.logger.warning(f"{desc} model not fitted.")
            return None

        missing = [f for f in required if f not in input_data]
        if missing:
            self.logger.error(f"Missing features for {desc}: {missing}")
            return None

        df = pd.DataFrame([input_data]).fillna(0)
        try:
            return model.predict(df)[0]
        except Exception as e:
            self.logger.error(f"Error predicting {desc}: {e}")
            return None

    # -------------------------------------------------------------------------
    # SECTION: COMBINING DATA & RETRAINING
    # -------------------------------------------------------------------------
    def combine_and_retrain(self, old_file: str, new_files: list) -> str:
        """
        Merge old + new CSVs to a single file, retrain both models, return combined file path.
        """
        try:
            if not os.path.exists(old_file):
                self.logger.error(f"Old data missing: {old_file}")
                return None
            combined = pd.read_csv(old_file)
            for f in new_files:
                if os.path.exists(f):
                    combined = pd.concat([combined, pd.read_csv(f)], ignore_index=True)
                else:
                    self.logger.warning(f"Skipping missing: {f}")

            out = 'combined_training_data.csv'
            combined.to_csv(out, index=False)
            self.logger.info(f"Combined data -> {out}")

            self.train_battery_life_model(out)
            self.train_net_current_model(out)
            return out
        except Exception as e:
            self.logger.error(f"Error combining/retraining: {e}")
            return None

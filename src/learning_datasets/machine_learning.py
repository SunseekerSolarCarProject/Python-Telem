# src/machine_learning.py

import os
import logging
import threading
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.exceptions import NotFittedError
from sklearn.utils.validation import check_is_fitted

class MachineLearningModel:
    def __init__(self, model_dir=None,
                 battery_life_model_file='battery_life_model.pkl',
                 break_even_model_file='break_even_speed_model.pkl'):
        self.logger = logging.getLogger(__name__)

        if model_dir is None:
            # Get current script directory and use a "models" subdirectory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            model_dir = os.path.join(current_dir, 'models')

        # Ensure model_dir exists
        os.makedirs(model_dir, exist_ok=True)

        # Construct full paths for the model files
        self.battery_life_model_path = os.path.join(model_dir, battery_life_model_file)
        self.break_even_model_path = os.path.join(model_dir, break_even_model_file)
        self.logger.info(f"Battery life model path: {self.battery_life_model_path}")
        self.logger.info(f"Break even model path: {self.break_even_model_path}")

        self.battery_life_model = None
        self.break_even_model = None

        # Now load the models (if they exist and are valid)
        self._load_battery_life_model()
        self._load_break_even_model()

    # -------------------------------------------------------------------------
    #                          Battery Life Model
    # -------------------------------------------------------------------------
    def _load_battery_life_model(self):
        if os.path.exists(self.battery_life_model_path):
            try:
                self.battery_life_model = joblib.load(self.battery_life_model_path)
                # Check if the loaded model is fitted.
                try:
                    check_is_fitted(self.battery_life_model)
                except NotFittedError:
                    self.logger.warning("Loaded battery life model is not fitted. It will be retrained.")
                    self.battery_life_model = None
                self.logger.info(f"Battery life model loaded from {self.battery_life_model_path}")
            except Exception as e:
                self.logger.error(f"Error loading battery life model: {e}")
                self.battery_life_model = None
        else:
            self.battery_life_model = None
            self.logger.info("No existing battery life model found. It will be created upon training.")

    def train_battery_life_model_in_thread(self, training_data_file, callback=None):
        training_thread = threading.Thread(
            target=self._train_battery_life_model_thread,
            args=(training_data_file, callback)
        )
        training_thread.start()

    def _train_battery_life_model_thread(self, training_data_file, callback):
        try:
            self.train_battery_life_model(training_data_file)
            if callback:
                callback()
        except Exception as e:
            self.logger.error(f"Error during battery life model training: {e}")
            if callback:
                callback(error=e)

    def train_battery_life_model(self, training_data_file):
        """
        Train the battery life model to predict 'Used_Ah_Remaining_Time'
        from columns: ['BP_ISH_Amps', 'BP_PVS_Voltage', 'BP_PVS_Ah']
        """
        if not os.path.exists(training_data_file):
            self.logger.error(f"Training data file {training_data_file} does not exist.")
            return

        try:
            data = pd.read_csv(training_data_file)

            required_columns = ['BP_ISH_Amps', 'BP_PVS_Voltage', 'BP_PVS_Ah', 'Used_Ah_Remaining_Time']
            for col in required_columns:
                if col not in data.columns:
                    self.logger.error(f"Column {col} not found in training data.")
                    return

            X = data[['BP_ISH_Amps', 'BP_PVS_Voltage', 'BP_PVS_Ah']].fillna(0)
            y = data['Used_Ah_Remaining_Time'].fillna(0)

            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
            self.battery_life_model = LinearRegression()
            self.battery_life_model.fit(X_train, y_train)

            # Save the trained model
            joblib.dump(self.battery_life_model, self.battery_life_model_path)
            self.logger.info(f"Battery life model trained and saved to {self.battery_life_model_path}")

            score = self.battery_life_model.score(X_test, y_test)
            self.logger.info(f"Battery life model R^2 score: {score}")

        except Exception as e:
            self.logger.error(f"Error training battery life model: {e}")

    def predict_battery_life(self, input_data):
        """
        Predict the battery life using the battery_life_model.
        :param input_data: dict with keys ['BP_ISH_Amps', 'BP_PVS_Voltage', 'BP_PVS_Ah']
        :return: float or None if error
        """
        if not self.battery_life_model:
            self.logger.warning("Battery life model is not trained. Cannot make prediction.")
            return None
        try:
            # Ensure the model is fitted before predicting
            try:
                check_is_fitted(self.battery_life_model)
            except NotFittedError:
                self.logger.warning("Battery life model is not fitted. Cannot make prediction.")
                return None

            required_features = ['BP_ISH_Amps', 'BP_PVS_Voltage', 'BP_PVS_Ah']
            for f in required_features:
                if f not in input_data:
                    self.logger.error(f"Missing feature '{f}' in input_data.")
                    return None

            df = pd.DataFrame([input_data]).fillna(0)
            prediction = self.battery_life_model.predict(df)
            self.logger.debug(f"Battery life prediction: {prediction[0]} with input data: {input_data}")
            return prediction[0]
        except Exception as e:
            self.logger.error(f"Error making battery life prediction: {e}")
            return None

    # -------------------------------------------------------------------------
    #                         Break-Even Speed Model
    # -------------------------------------------------------------------------
    def _load_break_even_model(self):
        if os.path.exists(self.break_even_model_path):
            try:
                self.break_even_model = joblib.load(self.break_even_model_path)
                try:
                    check_is_fitted(self.break_even_model)
                except NotFittedError:
                    self.logger.warning("Loaded break-even model is not fitted. It will be retrained.")
                    self.break_even_model = None
                self.logger.info(f"Break-even speed model loaded from {self.break_even_model_path}")
            except Exception as e:
                self.logger.error(f"Error loading break-even speed model: {e}")
                self.break_even_model = None
        else:
            self.break_even_model = None
            self.logger.info("No existing break-even speed model found. It will be created upon training.")

    def train_break_even_model_in_thread(self, training_data_file, callback=None):
        training_thread = threading.Thread(
            target=self._train_break_even_model_thread,
            args=(training_data_file, callback)
        )
        training_thread.start()

    def _train_break_even_model_thread(self, training_data_file, callback):
        try:
            self.train_break_even_model(training_data_file)
            if callback:
                callback()
        except Exception as e:
            self.logger.error(f"Error during break-even speed model training: {e}")
            if callback:
                callback(error=e)

    def train_break_even_model(self, training_data_file):
        """
        Train a model to predict the 'BreakEvenSpeed' from columns:
        ['Battery_Ah_Used', 'Velocity', 'MotorControllerCurrent']
        (In reality, you might label your data with a known break-even speed
         or compute net amps ~ 0. For now, we assume you have a 'BreakEvenSpeed' column.)
        """
        if not os.path.exists(training_data_file):
            self.logger.error(f"Training data file {training_data_file} does not exist.")
            return

        try:
            data = pd.read_csv(training_data_file)

            required_columns = ['Battery_Ah_Used', 'Velocity', 'MotorControllerCurrent', 'BreakEvenSpeed']
            for col in required_columns:
                if col not in data.columns:
                    self.logger.error(f"Column {col} not found in training data.")
                    return

            # Simple example features
            X = data[['Battery_Ah_Used', 'Velocity', 'MotorControllerCurrent']].fillna(0)
            y = data['BreakEvenSpeed'].fillna(0)

            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
            self.break_even_model = LinearRegression()
            self.break_even_model.fit(X_train, y_train)

            # Save the trained model
            joblib.dump(self.break_even_model, self.break_even_model_path)
            self.logger.info(f"Break-even speed model trained and saved to {self.break_even_model_path}")

            score = self.break_even_model.score(X_test, y_test)
            self.logger.info(f"Break-even speed model R^2 score: {score}")

        except Exception as e:
            self.logger.error(f"Error training break-even speed model: {e}")

    def predict_break_even_speed(self, input_data):
        """
        Predict the break-even speed using the break_even_model.
        :param input_data: dict with keys ['Battery_Ah_Used', 'Velocity', 'MotorControllerCurrent']
        :return: float or None if error
        """
        if not self.break_even_model:
            self.logger.warning("Break-even speed model is not trained. Cannot make prediction.")
            return None
        try:
            # Ensure the model is fitted before predicting
            try:
                check_is_fitted(self.break_even_model)
            except NotFittedError:
                self.logger.warning("Break-even speed model is not fitted. Cannot make prediction.")
                return None

            required_features = ['Battery_Ah_Used', 'Velocity', 'MotorControllerCurrent']
            for f in required_features:
                if f not in input_data:
                    self.logger.error(f"Missing feature '{f}' in input_data.")
                    return None

            df = pd.DataFrame([input_data]).fillna(0)
            prediction = self.break_even_model.predict(df)
            self.logger.debug(f"Break-even speed prediction: {prediction[0]} with input data: {input_data}")
            return prediction[0]
        except Exception as e:
            self.logger.error(f"Error making break-even speed prediction: {e}")
            return None

    # -------------------------------------------------------------------------
    #                  Combining Old Data & New Data for Retraining
    # -------------------------------------------------------------------------
    def combine_and_retrain(self, old_data_file, new_data_files):
        """
        Combines old and multiple new datasets into one CSV file for retraining.
        :param old_data_file: Path to the old data CSV.
        :param new_data_files: List of paths to new CSV files to combine.
        :return: Path to combined CSV or None if error.
        """
        try:
            if not os.path.exists(old_data_file):
                self.logger.error(f"Old data file {old_data_file} does not exist.")
                return None

            combined_data = pd.read_csv(old_data_file)
            for new_file in new_data_files:
                if os.path.exists(new_file):
                    new_data = pd.read_csv(new_file)
                    combined_data = pd.concat([combined_data, new_data], ignore_index=True)
                else:
                    self.logger.warning(f"New data file {new_file} does not exist. Skipping.")

            combined_filename = 'combined_training_data.csv'
            combined_data.to_csv(combined_filename, index=False)
            self.logger.info(f"Combined data saved to {combined_filename}")

            # Retrain both models using the combined dataset
            self.train_battery_life_model(combined_filename)
            self.train_break_even_model(combined_filename)

            return combined_filename
        except Exception as e:
            self.logger.error(f"Error combining data files: {e}")
            return None

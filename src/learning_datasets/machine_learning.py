# src/machine_learning.py

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
import joblib
import os
import logging
import threading

class MachineLearningModel:
    def __init__(self, model_file='battery_life_model.pkl'):
        self.model_file = model_file
        self.model = None
        self.logger = logging.getLogger(__name__)
        self.load_model()

    def load_model(self):
        if os.path.exists(self.model_file):
            try:
                self.model = joblib.load(self.model_file)
                self.logger.info(f"Model loaded from {self.model_file}")
            except Exception as e:
                self.logger.error(f"Error loading model: {e}")
                self.model = None
        else:
            self.model = None
            self.logger.info("No existing model found. Model will be created upon training.")

    def train_model_in_thread(self, training_data_file, callback=None):
        training_thread = threading.Thread(target=self._train_model_thread, args=(training_data_file, callback))
        training_thread.start()

    def _train_model_thread(self, training_data_file, callback):
        try:
            self.train_model(training_data_file)
            if callback:
                callback()
        except Exception as e:
            self.logger.error(f"Error during model training: {e}")
            if callback:
                callback(error=e)

    def train_model(self, training_data_file):
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
            self.model = LinearRegression()
            self.model.fit(X_train, y_train)

            # Save the trained model
            joblib.dump(self.model, self.model_file)
            self.logger.info(f"Model trained and saved to {self.model_file}")
            score = self.model.score(X_test, y_test)
            self.logger.info(f"Model evaluation score (R^2): {score}")

        except Exception as e:
            self.logger.error(f"Error training model: {e}")

    def predict(self, input_data):
        if not self.model:
            self.logger.warning("Model is not trained. Cannot make prediction.")
            return None
        try:
            required_features = ['BP_ISH_Amps', 'BP_PVS_Voltage', 'BP_PVS_Ah']
            for f in required_features:
                if f not in input_data:
                    self.logger.error(f"Missing feature '{f}' in input_data.")
                    return None

            df = pd.DataFrame([input_data]).fillna(0)
            prediction = self.model.predict(df)
            self.logger.debug(f"Made prediction: {prediction[0]} with input data: {input_data}")
            return prediction[0]
        except Exception as e:
            self.logger.error(f"Error making prediction: {e}")
            return None

    def combine_and_retrain(self, old_data_file, new_data_files):
        """
        Combines old and multiple new datasets into one CSV file for retraining.
        :param old_data_file: Path to the old data CSV.
        :param new_data_files: List of paths to new CSV files to combine.
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

            # Retrain the model with the combined data
            self.train_model(combined_filename)
            return combined_filename
        except Exception as e:
            self.logger.error(f"Error combining data files: {e}")
            return None
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
        """
        Loads the machine learning model from a file if it exists.
        """
        if os.path.exists(self.model_file):
            self.model = joblib.load(self.model_file)
            self.logger.info(f"Model loaded from {self.model_file}")
        else:
            self.model = None
            self.logger.info("No existing model found. A new model will be trained.")

    def train_model_in_thread(self, training_data_file, callback=None):
        """
        Trains the machine learning model in a separate thread.
        :param training_data_file: Path to the training data CSV file.
        :param callback: Optional callback function to call after training is complete.
        """
        training_thread = threading.Thread(target=self._train_model_thread, args=(training_data_file, callback))
        training_thread.start()

    def _train_model_thread(self, training_data_file, callback):
        """
        The actual training method that runs in a separate thread.
        """
        try:
            self.train_model(training_data_file)
            if callback:
                callback()
        except Exception as e:
            self.logger.error(f"Error during model training: {e}")
            if callback:
                callback(error=e)
    
    def train_model(self, training_data_file):
        """
        Trains the machine learning model using the provided training data.
        """
        try:
            data = pd.read_csv(training_data_file)
            # Select features and target variable
            X = data[['BP_ISH_Amps', 'BP_PVS_Voltage', 'BP_PVS_Ah']]  # Features
            y = data['Used_Ah_Remaining_Time']  # Target variable

            # Handle missing values
            X = X.fillna(0)
            y = y.fillna(0)

            # Split data into training and testing sets
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

            # Initialize and train the model
            self.model = LinearRegression()
            self.model.fit(X_train, y_train)

            # Save the trained model
            joblib.dump(self.model, self.model_file)
            self.logger.info(f"Model trained and saved to {self.model_file}")

            # Optionally, evaluate the model
            score = self.model.score(X_test, y_test)
            self.logger.info(f"Model evaluation score: {score}")

        except Exception as e:
            self.logger.error(f"Error training model: {e}")

    def predict(self, input_data):
        """
        Makes a prediction using the trained model.
        :param input_data: Dictionary with keys matching the features used in training.
        :return: Predicted value.
        """
        if not self.model:
            self.logger.warning("Model is not trained. Prediction cannot be made.")
            return None
        try:
            df = pd.DataFrame([input_data])
            df = df.fillna(0)
            prediction = self.model.predict(df)
            self.logger.debug(f"Made prediction: {prediction[0]} with input data: {input_data}")
            return prediction[0]
        except Exception as e:
            self.logger.error(f"Error making prediction: {e}")
            return None


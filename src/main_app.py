# src/main_app.py

import sys
import os
import logging
import requests
import joblib
import pandas
import sklearn
import json
import dotenv
import logging.handlers
import numpy
import serial
import serial.tools.list_ports
import pyqtgraph
from telemetry_application import TelemetryApplication
from PyQt6.QtWidgets import QApplication
from central_logger import CentralLogger  # Import the CentralLogger class

def main():

    # Set default logging level
    default_log_level = 'INFO'
    log_level = getattr(logging, default_log_level.upper(), logging.INFO)

    # Determine base directory:
    #  - if bundled as an .exe (PyInstaller, cx_Freeze, etc.), use sys.executable
    #  - otherwise (running as a script), use __file__
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    # ---------------------------------------------------------------------
    # 1) Create/ensure a centralized folder for logs and CSV
    # ---------------------------------------------------------------------
    storage_folder = os.path.join(base_dir, "application_data")
    os.makedirs(storage_folder, exist_ok=True)

    # Build the log file path in our storage folder
    log_file_path = os.path.join(storage_folder, 'telemetry_application.log')

    # Initialize the centralized logger with the folder path
    central_logger = CentralLogger(log_file=log_file_path, level=log_level)

    # Initialize QApplication
    app = QApplication(sys.argv)

    # ---------------------------------------------------------------------
    # 2) Initialize TelemetryApplication with a reference to the same folder
    # ---------------------------------------------------------------------
    telemetry_app = TelemetryApplication(
        app=app,
        storage_folder=storage_folder,  # Pass along to handle CSV files
    )
    startup_success = telemetry_app.start()

    if not startup_success:
        # Exit the application if configuration was canceled or failed
        central_logger.get_logger(__name__).info("Startup failed or was canceled. Exiting application.")
        sys.exit(0)

    # Run the PyQt6 event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

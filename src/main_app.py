# src/main_app.py

# imports for making the application to work when using the auto-py-to-exe tool
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
import shutil
import sklearn.pipeline
import sklearn.ensemble
import sklearn.exceptions
import sklearn.utils.validation
import tufup.utils
import tufup.client
from tufup.client import Client  # More specific import
from Version import VERSION
from telemetry_application import TelemetryApplication
from updater.update_checker import UpdateChecker  # Import the UpdateChecker class
from PyQt6.QtWidgets import QApplication, QMessageBox
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

    #-------------------------------------------------------------------------
    # initialize the UpdateChecker with metadata URL and download directory
    #-------------------------------------------------------------------------
    uc = UpdateChecker(
        repo_owner="SunseekerSolarCarProject",
        repo_name="Python-Telem",
        version=VERSION,
        app_install_dir=base_dir
    )
    if uc.check_for_updates():
        reply = QMessageBox.question(
            None,
            "Update Available",
            f"A new version is available (you’re on v{VERSION}).\n"
            "Download and install now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            uc.download_and_apply_update()
            # download_and_apply_update() never returns—your app will restart.

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

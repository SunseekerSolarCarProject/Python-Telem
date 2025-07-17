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
    update_checker = UpdateChecker(
        metadata_url="https://github.com/SunseekerSolarCarProject/Python-Telem/releases/latest",  # Replace with your update server URL
        download_dir=os.path.join(storage_folder, "updates")
    )
    
    # Check for updates
    if update_checker.check_for_updates():
        reply = QMessageBox.question(
            None, 
            'Update Available',
            'A new version is available. Would you like to update now?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if update_checker.download_and_apply_update():
                QMessageBox.information(
                    None,
                    'Update Successful',
                    'The application has been updated. Please restart to apply changes.'
                )
                sys.exit(0)

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

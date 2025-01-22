# src/main_app.py

import sys
import os
import logging
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

    # Add the parent directory to the system path (if necessary)
    sys.path.append(os.path.abspath(os.path.dirname(__file__)))

    # ---------------------------------------------------------------------
    # 1) Create/ensure a centralized folder for logs and CSV
    # ---------------------------------------------------------------------
    storage_folder = os.path.join(os.path.dirname(__file__), "application_data")
    if not os.path.exists(storage_folder):
        os.makedirs(storage_folder)

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

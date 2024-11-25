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
    default_log_level = 'INFO'  # You can choose to set this in config.json or elsewhere

    # Map string log level to logging module levels
    log_level = getattr(logging, default_log_level.upper(), logging.INFO)

    # Add the parent directory to the system path (if necessary)
    sys.path.append(os.path.abspath(os.path.dirname(__file__)))

    # Initialize the centralized logger
    central_logger = CentralLogger(log_file='telemetry_application.log', level=log_level)

    # Initialize QApplication
    app = QApplication(sys.argv)

    # Initialize TelemetryApplication without command-line args
    telemetry_app = TelemetryApplication(
        app=app,  # Pass the QApplication instance
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

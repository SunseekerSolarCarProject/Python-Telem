# main_app.py

import sys
import os
import logging
import argparse
from telemetry_application import TelemetryApplication
from PyQt6.QtWidgets import QApplication
from central_logger import CentralLogger  # Import the CentralLogger class

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Telemetry Application')
    parser.add_argument('--baudrate', type=int, default=9600, help='Serial baud rate')
    parser.add_argument('--loglevel', type=str, default='INFO', help='Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
    args = parser.parse_args()

    # Map string log level to logging module levels
    log_level = getattr(logging, args.loglevel.upper(), logging.DEBUG)

    # Add the parent directory to the system path
    sys.path.append(os.path.abspath(os.path.dirname(__file__)))

    # Initialize the centralized logger
    central_logger = CentralLogger(log_file='telemetry_application.log', level=log_level)

    # Initialize QApplication
    app = QApplication(sys.argv)

    # Initialize TelemetryApplication
    telemetry_app = TelemetryApplication(
        baudrate=args.baudrate,
        log_level=log_level,
        app=app,  # Pass the QApplication instance
        central_logger=central_logger  # Pass the CentralLogger instance
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

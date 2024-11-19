# main.py

import logging
import argparse
from telemetry_application import TelemetryApplication

def main():
    #current baudrate for faster data processing is 115200 if needed.
    parser = argparse.ArgumentParser(description='Telemetry Application')
    parser.add_argument('--baudrate', type=int, default=9600, help='Serial baud rate')
    parser.add_argument('--loglevel', type=str, default='INFO', help='Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
    args = parser.parse_args()

    # Map string log level to logging module levels
    log_level = getattr(logging, args.loglevel.upper(), logging.INFO)

    app = TelemetryApplication(baudrate=args.baudrate, log_level=log_level)
    app.start()

if __name__ == "__main__":
    main()
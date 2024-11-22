# serial_reader.py

from PyQt6.QtCore import QThread, pyqtSignal
import serial
import serial.tools.list_ports
import logging
import json

class SerialReaderThread(QThread):
    data_received = pyqtSignal(dict)  # Processed data as a dictionary
    raw_data_received = pyqtSignal(str)  # Raw hex data as a string

    def __init__(self, port, baudrate, process_data_callback=None, process_raw_data_callback=None):
        """
        Initializes the SerialReaderThread.

        :param port: Serial port to connect to (e.g., 'COM3').
        :param baudrate: Baud rate for the serial communication (e.g., 9600).
        :param process_data_callback: Optional callback function for processed data.
        :param process_raw_data_callback: Optional callback function for raw data.
        """
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.process_data_callback = process_data_callback
        self.process_raw_data_callback = process_raw_data_callback
        self.running = True
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)  # Set to DEBUG for detailed logs

    def run(self):
        """
        The main loop that reads data from the serial port.
        """
        try:
            with serial.Serial(self.port, self.baudrate, timeout=1) as ser:
                self.logger.info(f"Serial port {self.port} opened with baudrate {self.baudrate}.")
                while self.running:
                    if ser.in_waiting:
                        raw_line = ser.readline().decode('utf-8', errors='replace').strip()
                        if raw_line:
                            self.logger.debug(f"Raw data read from serial: {raw_line}")
                            # Emit raw data signal
                            self.raw_data_received.emit(raw_line)
                            # Optionally, process the raw data
                            processed_data = self.process_raw_line(raw_line)
                            if processed_data:
                                self.data_received.emit(processed_data)
        except serial.SerialException as e:
            self.logger.error(f"Serial exception: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in SerialReaderThread: {e}")

    def process_raw_line(self, raw_line):
        """
        Processes a raw line from the serial port into a dictionary.

        :param raw_line: Raw string data from serial.
        :return: Dictionary containing processed telemetry data or None if processing fails.
        """
        try:
            # Example Processing:
            # Assuming raw_line is a JSON string. Adjust parsing logic as per your data format.
            telemetry_data = json.loads(raw_line)
            if isinstance(telemetry_data, dict):
                self.logger.debug(f"Processed telemetry data: {telemetry_data}")
                return telemetry_data
            else:
                self.logger.warning(f"Processed data is not a dictionary: {telemetry_data}")
                return None
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to decode JSON from raw line: {raw_line}. Error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error processing raw line: {raw_line}. Exception: {e}")
            return None

    def stop(self):
        """
        Stops the thread gracefully.
        """
        self.running = False
        self.wait()
        self.logger.info("SerialReaderThread stopped.")

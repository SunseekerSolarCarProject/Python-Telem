# src/serial_reader.py

from PyQt6.QtCore import QThread, pyqtSignal
import serial
import serial.tools.list_ports
import logging

class SerialReaderThread(QThread):
    data_received = pyqtSignal(str)  # Emit raw lines as strings
    raw_data_received = pyqtSignal(str)  # Optionally, emit raw lines separately

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
        self.logger.info("Serial reader initialized.")

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
                            self.data_received.emit(raw_line)
                            # Optionally, emit raw data separately
                            self.raw_data_received.emit(raw_line)
        except serial.SerialException as e:
            self.logger.error(f"Serial exception: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in SerialReaderThread: {e}")

    def stop(self):
        """
        Stops the thread gracefully.
        """
        self.running = False
        self.wait()
        self.logger.info("SerialReaderThread stopped.")

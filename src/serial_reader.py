# src/serial_reader.py

import sys
import logging
import serial
import serial.tools.list_ports
from PyQt6.QtCore import QThread, pyqtSignal

class SerialReaderThread(QThread):
    data_received     = pyqtSignal(str)
    raw_data_received = pyqtSignal(str)

    def __init__(self, port: str, baudrate: int,
                 process_data_callback=None,
                 process_raw_data_callback=None,
                 parent=None):
        """
        :param port: Serial port (e.g. 'COM3' or '/dev/tty.usbmodem14101')
        :param baudrate: e.g. 9600
        """
        super().__init__(parent)
        self.port      = port
        self.baudrate  = baudrate
        self.running   = True

        # Optional callbacks
        self.process_data_callback     = process_data_callback
        self.process_raw_data_callback = process_raw_data_callback

        # Use module-level logger; inherit root handlers/level
        self.logger = logging.getLogger(__name__)
        # Respect global logging configuration; do not add handlers here
        self.logger.debug(f"Initialized SerialReaderThread on {self.port}@{self.baudrate}")

    @staticmethod
    def get_available_ports() -> list[str]:
        """
        Cross-platform list of serial ports:
          - Windows: ['COM1', 'COM2', ...]
          - macOS:   ['/dev/cu.usbserial-...', '/dev/tty.usbmodem-...', ...]
          - Linux:   ['/dev/ttyUSB0', '/dev/ttyACM0', ...]
        """
        ports = [p.device for p in serial.tools.list_ports.comports()]
        if sys.platform.startswith("win"):
            return ports
        elif sys.platform.startswith("darwin"):
            return [p for p in ports if p.startswith("/dev/cu.") or p.startswith("/dev/tty.")]
        else:
            return [p for p in ports if p.startswith("/dev/ttyUSB") or p.startswith("/dev/ttyACM")]

    def run(self):
        """
        Main loop: open port and emit lines as they arrive.
        """
        try:
            with serial.Serial(self.port, self.baudrate, timeout=1) as ser:
                self.logger.info(f"Opened serial port {self.port} at {self.baudrate}")
                while self.running:
                    if ser.in_waiting:
                        raw_line = ser.readline().decode('utf-8', errors='replace').strip()
                        if raw_line:
                            # Only debug-log if level allows
                            self.logger.debug(f"Raw data: {raw_line}")
                            self.data_received.emit(raw_line)
                            self.raw_data_received.emit(raw_line)
        except serial.SerialException as e:
            self.logger.error(f"SerialException: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in SerialReaderThread: {e}")

    def stop(self):
        """
        Gracefully stop the thread.
        """
        self.running = False
        self.wait()
        self.logger.info("SerialReaderThread stopped.")

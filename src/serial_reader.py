# src/serial_reader.py

import sys
import logging
import glob
import os
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
          - Linux:   ['/dev/ttyUSB0', '/dev/ttyACM0', '/dev/pts/3', ...]
        """
        ports = [p.device for p in serial.tools.list_ports.comports()]
        if sys.platform.startswith("win"):
            return ports
        elif sys.platform.startswith("darwin"):
            return [p for p in ports if p.startswith("/dev/cu.") or p.startswith("/dev/tty.")]
        else:
            linux_ports = [
                p for p in ports
                if p.startswith(("/dev/ttyUSB", "/dev/ttyACM", "/dev/ttyS"))
            ]
            # socat-created virtual serial endpoints are often /dev/pts/N and
            # are not reliably returned by pyserial's list_ports on Linux.
            for pts_path in glob.glob("/dev/pts/[0-9]*"):
                if os.access(pts_path, os.R_OK | os.W_OK):
                    linux_ports.append(pts_path)
            return sorted(dict.fromkeys(linux_ports))

    def run(self):
        """
        Main loop: open port and emit lines as they arrive.
        """
        try:
            with serial.Serial(self.port, self.baudrate, timeout=1) as ser:
                self.logger.info(f"Opened serial port {self.port} at {self.baudrate}")
                while self.running:
                    # PTYs created by socat do not always report in_waiting
                    # consistently. readline() already respects timeout=1, so
                    # it works for both virtual ports and physical serial ports.
                    raw_line = ser.readline().decode('utf-8', errors='replace').strip()
                    if raw_line:
                        # Emit both streams: one is parsed into fields, the other is
                        # archived verbatim so bad parser assumptions can be audited.
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

# serial_reader.py

import serial
import threading
import time
import logging

class SerialReaderThread(threading.Thread):
    def __init__(self, port, baudrate, process_data_callback, process_raw_data_callback):
        super().__init__(daemon=True)
        self.logger = logging.getLogger(__name__)
        self.port = port
        self.baudrate = baudrate
        self.process_data_callback = process_data_callback
        self.process_raw_data_callback = process_raw_data_callback
        self.serial_conn = None
        self._stop_event = threading.Event()
        self.logger.info(f"SerialReaderThread initialized on port {port} with baudrate {baudrate}")

    def run(self):
        try:
            self.logger.info(f"Attempting to open serial port {self.port} at {self.baudrate} baud.")
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            # Increase buffer size to 4MB
            self.serial_conn.set_buffer_size(rx_size=4 * 1024 * 1024, tx_size=4 * 1024 * 1024)
            self.logger.info("Serial port opened and buffer size set to 4MB.")

            while not self._stop_event.is_set():
                if self.serial_conn.in_waiting > 0:
                    try:
                        raw_bytes = self.serial_conn.readline()
                        raw_data = raw_bytes.decode('utf-8', errors='replace').strip()
                        self.logger.debug(f"Raw data received: {raw_data}")
                        self.process_raw_data_callback(raw_data)
                        self.process_data_callback(raw_data)
                    except Exception as e:
                        self.logger.error(f"Error reading from serial port: {e}")
                else:
                    self.logger.debug("No data in serial buffer.")
                time.sleep(0.1)
        except serial.SerialException as e:
            self.logger.error(f"Serial error: {e}")
            print(f"Serial error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in SerialReaderThread: {e}")
        finally:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
                self.logger.info(f"Serial port {self.port} closed.")

    def stop(self):
        self.logger.info("Stopping SerialReaderThread.")
        self._stop_event.set()

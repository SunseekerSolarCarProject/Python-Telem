# serial_reader.py

import serial
import threading
import time

class SerialReaderThread(threading.Thread):
    def __init__(self, port, baudrate, process_data_callback):
        super().__init__(daemon=True)
        self.port = port
        self.baudrate = baudrate
        self.process_data_callback = process_data_callback
        self.serial_conn = None
        self._stop_event = threading.Event()
    
    def run(self):
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            # Increase buffer size to 4MB
            self.serial_conn.set_buffer_size(rx_size=4 * 1024 * 1024, tx_size=4 * 1024 * 1024)
            while not self._stop_event.is_set():
                if self.serial_conn.in_waiting > 0:
                    data = self.serial_conn.readline().decode('utf-8').strip()
                    self.process_data_callback(data)
                time.sleep(0.1)
        except serial.SerialException as e:
            print(f"Serial error: {e}")
        finally:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()

    def stop(self):
        self._stop_event.set()

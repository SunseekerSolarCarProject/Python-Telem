# buffer_data.py

import time
from datetime import datetime
import logging
import csv
from data_processor import DataProcessor

class BufferData:
    def __init__(self, csv_headers, secondary_csv_headers, buffer_size, buffer_timeout):
        self.logger = logging.getLogger(__name__)
        self.dataprocessor = DataProcessor()
        self.csv_headers = csv_headers
        self.secondary_csv_headers = secondary_csv_headers
        self.buffer_size = buffer_size
        self.buffer_timeout = buffer_timeout
        self.data_buffer = []  # Holds processed data entries
        self.raw_data_buffer = []  # Holds raw hex data entries
        self.last_flush_time = time.time()
        self.combined_data = {}  # Holds the latest values for each telemetry field
        self.logger.info(f"BufferData initialized with buffer_size={buffer_size}, buffer_timeout={buffer_timeout}")

    def add_data(self, data):
        """
        Add processed telemetry data to the buffer and update combined_data.
        """
        self.data_buffer.append(data)
        self.logger.debug(f"Data added to data_buffer: {data}")
        self.update_combined_data(data)

        # Determine if buffer is ready to flush based on size or timeout
        buffer_ready = len(self.data_buffer) >= self.buffer_size or \
                (time.time() - self.last_flush_time) >= self.buffer_timeout
        self.logger.debug(f"Buffer size: {len(self.data_buffer)}, Time since last flush: {time.time() - self.last_flush_time:.2f}s")
        if buffer_ready:
            self.logger.debug("Buffer is ready to flush.")
            return True  # Ready to flush

        return False

    def update_combined_data(self, new_data):
        """
        Updates the combined_data dictionary with new data.
        """
        self.combined_data.update(new_data)
        self.logger.debug(f"Combined data updated with: {new_data}")

    def add_raw_data(self, raw_data, filename):
        """
        Add raw hex data to the raw data buffer and flush if needed.
        """
        self.raw_data_buffer.append(raw_data)
        self.logger.debug(f"Raw data added to raw_data_buffer: {raw_data}")
        if len(self.raw_data_buffer) >= self.buffer_size:
            self.logger.debug("Raw data buffer is full. Flushing raw data buffer.")
            self.flush_raw_data_buffer(filename)

    def flush_raw_data_buffer(self, filename):
        """
        Flush the raw hex data buffer to the secondary CSV file.
        """
        if not self.raw_data_buffer:
            self.logger.debug("Raw data buffer is empty. Nothing to flush.")
            return  # Nothing to flush

        try:
            with open(filename, mode='a', newline='') as file:
                writer = csv.writer(file)
                for raw_data_entry in self.raw_data_buffer:
                    row = [raw_data_entry.get(header, '') for header in self.secondary_csv_headers]
                    writer.writerow(row)
            self.logger.debug(f"Flushed raw data buffer to file: {filename}")
        except Exception as e:
            self.logger.error(f"Error flushing raw data buffer to file {filename}: {e}")
        finally:
            self.raw_data_buffer.clear()
            self.logger.debug("Raw data buffer cleared after flushing.")

    def flush_buffer(self, filename, battery_info, used_ah):
        """
        Flush the combined data to the primary CSV file.
        """
        if not self.data_buffer:
            self.logger.debug("Data buffer is empty. Nothing to flush.")
            return None  # Nothing to flush

        # Fill missing fields with default values
        for field in self.csv_headers:
            self.combined_data.setdefault(field, "N/A")

        # Add battery-related metrics
        shunt_current = self.safe_float(self.combined_data.get('BP_ISH_Amps', 0))
        self.combined_data.update(battery_info)
        self.combined_data['remaining_Ah'] = self.dataprocessor.calculate_remaining_capacity(
            used_ah, self.safe_float(self.combined_data.get('Total_Capacity_Ah', 0.0)), shunt_current)
        self.combined_data['remaining_wh'] = self.dataprocessor.calculate_watt_hours(
            self.combined_data['remaining_Ah'], self.safe_float(self.combined_data.get('Total_Voltage', 0.0)))
        self.combined_data['remaining_time'] = self.dataprocessor.calculate_remaining_time(
            self.combined_data['remaining_Ah'], shunt_current)

        self.logger.debug(f"Combined data with battery info: {self.combined_data}")

        # Write to CSV
        try:
            self.append_to_csv(filename, self.combined_data)
            self.logger.debug(f"Data appended to CSV file: {filename}")
        except Exception as e:
            self.logger.error(f"Error writing to CSV file {filename}: {e}")

        # Clear the data buffer and reset flush time
        self.data_buffer.clear()
        self.last_flush_time = time.time()
        self.logger.debug("Data buffer cleared and last_flush_time reset.")

        self.logger.debug(f"Final combined_data after processing: {self.combined_data}")
        return self.combined_data

    def append_to_csv(self, filename, data):
        """
        Append a single row of data to the specified CSV file.
        """
        row = [data.get(header, '') for header in self.csv_headers]
        try:
            with open(filename, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(row)
            self.logger.debug(f"Appended row to CSV file {filename}: {row}")
        except Exception as e:
            self.logger.error(f"Error appending row to CSV file {filename}: {e}")

    def safe_float(self, value, default=0.0):
        """
        Safely convert a value to a float, returning a default if conversion fails.
        """
        try:
            result = float(value)
            self.logger.debug(f"Converted value to float: {value} -> {result}")
            return result
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Unable to convert value to float: {value}. Using default {default}. Exception: {e}")
            return default

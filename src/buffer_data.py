# src/buffer_data.py

import time
from datetime import datetime
import logging
from extra_calculations import ExtraCalculations

class BufferData:
    def __init__(self, csv_handler, csv_headers, secondary_csv_headers, buffer_size, buffer_timeout):
        """
        Initializes the BufferData with the given parameters and CSVHandler.

        :param csv_handler: Instance of CSVHandler to manage CSV operations.
        :param csv_headers: List of headers for the primary CSV file.
        :param secondary_csv_headers: List of headers for the secondary CSV file.
        :param buffer_size: Number of data points before the buffer flushes.
        :param buffer_timeout: Time in seconds before the buffer flushes data.
        """
        self.logger = logging.getLogger(__name__)
        self.extra_calculations = ExtraCalculations()
        self.csv_handler = csv_handler  # Use the passed CSVHandler instance
        self.csv_headers = csv_headers
        self.secondary_csv_headers = secondary_csv_headers
        self.buffer_size = buffer_size
        self.buffer_timeout = buffer_timeout
        self.data_buffer = []  # Holds processed data entries for primary CSV
        self.raw_data_buffer = []  # Holds raw hex data entries for secondary CSV
        self.last_flush_time = time.time()
        self.combined_data = {}  # Holds the latest values for each telemetry field
        self.logger.info(f"BufferData initialized with buffer_size={buffer_size}, buffer_timeout={buffer_timeout}")

    def add_data(self, data):
        """
        Add processed telemetry data to the buffer and update combined_data.

        :param data: Dictionary containing processed telemetry data.
        :return: True if the buffer is ready to flush, False otherwise.
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

        :param new_data: Dictionary containing new telemetry data.
        """
        self.combined_data.update(new_data)
        self.logger.debug(f"Combined data updated with: {new_data}")

    def is_ready_to_flush(self):
        """
        Determines if the buffer is ready to flush based on timeout or size.

        :return: True if the buffer is ready to flush, False otherwise.
        """
        current_time = time.time()
        elapsed_time = current_time - self.last_flush_time
        return len(self.data_buffer) >= self.buffer_size or elapsed_time >= self.buffer_timeout

    def add_raw_data(self, raw_data, filename):
        """
        Add raw hex data to the raw data buffer and flush if needed.

        :param raw_data: String containing raw hex data.
        :param filename: Path to the secondary CSV file.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        raw_entry = {"timestamp": timestamp, "raw_data": raw_data}
        self.raw_data_buffer.append(raw_entry)
        self.logger.debug(f"Raw data added to raw_data_buffer: {raw_entry}")
        
        if len(self.raw_data_buffer) >= self.buffer_size:
            self.logger.debug("Raw data buffer is full. Flushing raw data buffer.")
            self.flush_raw_data_buffer(filename)

    def flush_raw_data_buffer(self, filename):
        """
        Flush the raw hex data buffer to the secondary CSV file.

        :param filename: Path to the secondary CSV file.
        """
        if not self.raw_data_buffer:
            self.logger.debug("Raw data buffer is empty. Nothing to flush.")
            return  # Nothing to flush

        for raw_data_entry in self.raw_data_buffer:
            if not isinstance(raw_data_entry, dict):
                self.logger.error(f"raw_data_entry is not a dict: {raw_data_entry} (type: {type(raw_data_entry)})")
                continue  # Skip this entry or handle it accordingly
            self.csv_handler.append_to_csv(filename, raw_data_entry)  # Pass dict

        self.raw_data_buffer.clear()
        self.logger.debug("Raw data buffer cleared after flushing.")

    def flush_buffer(self, filename, battery_info, used_ah):
        """
        Flush the combined data to the primary CSV file.

        :param filename: Path to the primary CSV file.
        :param battery_info: Dictionary containing battery-related information.
        :param used_ah: Float representing used Amp-Hours.
        :return: Combined data dictionary after processing.
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
        self.combined_data['Shunt_Remaining_Ah'] = self.extra_calculations.calculate_remaining_capacity(
            used_ah, self.safe_float(self.combined_data.get('Total_Capacity_Ah', 0.0)), shunt_current)
        self.combined_data['Shunt_Remaining_wh'] = self.extra_calculations.calculate_watt_hours(
            self.combined_data['Shunt_Remaining_Ah'], self.safe_float(self.combined_data.get('BP_PVS_Voltage', 0.0)))
        self.combined_data['Shunt_Remaining_Time'] = self.extra_calculations.calculate_remaining_time_hours(
            self.combined_data['Shunt_Remaining_Ah'], shunt_current)

        # Calculate remaining time using BP_PVS_Ah
        bp_pvs_ah = self.safe_float(self.combined_data.get('BP_PVS_Ah', 0))
        self.combined_data['Used_Ah_Remaining_Ah'] = self.extra_calculations.calculate_remaining_capacity_from_ah(
            used_ah, self.safe_float(self.combined_data.get('Total_Capacity_Ah')), bp_pvs_ah)
        self.logger.debug(f"Used Ah: {used_ah}, BP_PVS_Ah: {bp_pvs_ah}")
        self.combined_data['Used_Ah_Remaining_wh'] = self.extra_calculations.calculate_watt_hours(
            self.combined_data['Used_Ah_Remaining_Ah'], self.safe_float(self.combined_data.get('BP_PVS_Voltage', 0.0)))
        self.combined_data['Used_Ah_Remaining_Time'] = self.extra_calculations.calculate_remaining_time_from_ah_hours(
            self.combined_data['Used_Ah_Remaining_Ah'], bp_pvs_ah)

        self.logger.debug(f"Combined data with battery info: {self.combined_data}")

        # Append data to primary CSV
        self.csv_handler.append_to_csv(filename, self.combined_data)
        self.data_buffer.clear()
        self.last_flush_time = time.time()
        self.logger.debug("Data buffer cleared and last_flush_time reset.")
        self.logger.debug(f"Final combined_data after processing: {self.combined_data}")
        return self.combined_data

    def safe_float(self, value, default=0.0):
        """
        Safely convert a value to a float, returning a default if conversion fails.

        :param value: The value to convert.
        :param default: The default value to return if conversion fails.
        :return: Float value or default.
        """
        try:
            result = float(value)
            self.logger.debug(f"Converted value to float: {value} -> {result}")
            return result
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Unable to convert value to float: {value}. Using default {default}. Exception: {e}")
            return default

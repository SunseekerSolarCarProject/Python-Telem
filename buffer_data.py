#buffer_data.py
import time
from datetime import datetime
import csv


class BufferData:
    def __init__(self, csv_headers, secondary_csv_headers, buffer_size, buffer_timeout):
        self.csv_headers = csv_headers
        self.secondary_csv_headers = secondary_csv_headers
        self.buffer_size = buffer_size
        self.buffer_timeout = buffer_timeout
        self.data_buffer = []  # Holds processed data
        self.raw_data_buffer = []  # Holds raw hex data
        self.last_flush_time = time.time()
        self.ready_to_flush = False
        self.is_initialized = False

    def add_data(self, data):
        """
        Add processed telemetry data to the buffer.
        """
        self.data_buffer.append(data)

        if not self.is_initialized:
            # Check initialization status by combining data
            combined_data = self.get_combined_data()
            missing_fields = set(self.csv_headers) - combined_data.keys()

            if not missing_fields:
                print("Initialization complete. Buffer is now ready to flush.")
                self.is_initialized = True
                self.ready_to_flush = True
            else:
                print(f"Initialization in progress. Missing fields: {missing_fields}")
                return False

        # Determine if buffer is ready to flush
        if len(self.data_buffer) >= self.buffer_size or \
                (time.time() - self.last_flush_time) >= self.buffer_timeout:
            return True  # Ready to flush

        return False

    def add_raw_data(self, raw_data):
        """
        Add raw hex data to the raw data buffer.
        """
        self.raw_data_buffer.append(raw_data)
        if len(self.raw_data_buffer) >= self.buffer_size:
            self.flush_raw_data_buffer()

    def flush_raw_data_buffer(self, filename):
        """
        Flush the raw hex data buffer to the secondary CSV file.
        """
        if not self.raw_data_buffer:
            return  # Nothing to flush

        with open(filename, mode='a', newline='') as file:
            writer = csv.writer(file)
            for raw_data_entry in self.raw_data_buffer:
                row = [raw_data_entry.get(header, '') for header in self.secondary_csv_headers]
                writer.writerow(row)

        # Clear the raw data buffer
        self.raw_data_buffer.clear()

    def get_combined_data(self):
        """
        Combine all data in the buffer into a single dictionary.
        """
        combined_data = {}
        for data in self.data_buffer:
            combined_data.update(data)
        return combined_data

    def update_current_entry(self, partial_data):
        """
        Updates the most recent buffer entry with additional data.
        If the buffer is empty, create a new entry.
        """
        if self.data_buffer:
            # Update the most recent entry with partial data
            self.data_buffer[-1].update(partial_data)
        else:
            # If the buffer is empty, create a new entry
            self.data_buffer.append(partial_data)

    def is_buffer_complete(self, combined_data):
        """
        Checks if `combined_data` contains all required telemetry fields.
        """
        missing_fields = set(self.csv_headers) - combined_data.keys()
        return not missing_fields  # True if no fields are missing

    def flush_buffer(self, filename, data_processor, battery_info, used_ah):
        """
        Flush the buffer to the primary CSV file after validating completeness.
        """
        if not self.data_buffer or not self.ready_to_flush:
            print("Buffer not ready to flush. Waiting for complete data.")
            return None

        combined_data = self.get_combined_data()

        # Check for completeness
        missing_fields = set(self.csv_headers) - combined_data.keys()
        if missing_fields:
            print(f"Buffer incomplete, waiting for more data. Missing fields: {missing_fields}")
            return None

        # Fill missing fields with defaults
        for field in self.csv_headers:
            if field not in combined_data:
                combined_data[field] = "N/A"

        # Parse additional fields if required (e.g., motor controller data)
        if "MC1LIM" not in combined_data:
            combined_data["MC1LIM"] = data_processor.parse_motor_controller_data(
                combined_data.get("MC1LIM_Hex1", "0x00000000"),
                combined_data.get("MC1LIM_Hex2", "0x00000000")
            )
        if "MC2LIM" not in combined_data:
            combined_data["MC2LIM"] = data_processor.parse_motor_controller_data(
                combined_data.get("MC2LIM_Hex1", "0x00000000"),
                combined_data.get("MC2LIM_Hex2", "0x00000000")
            )

        # Add timestamps if missing
        combined_data['timestamp'] = combined_data.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        combined_data['device_timestamp'] = combined_data.get('device_timestamp', 'N/A')

        # Calculate battery-related metrics
        shunt_current = float(combined_data.get('BP_ISH_Amps', 0))
        combined_data['Total_Capacity_Wh'] = battery_info.get('Total_Capacity_Wh', 0.0)
        combined_data['Total_Capacity_Ah'] = battery_info.get('Total_Capacity_Ah', 0.0)
        combined_data['Total_Voltage'] = battery_info.get('Total_Voltage', 0.0)

        # Remaining metrics
        combined_data['remaining_Ah'] = data_processor.calculate_remaining_capacity(
            used_ah, combined_data['Total_Capacity_Ah'], shunt_current, 1)
        combined_data['remaining_wh'] = data_processor.calculate_watt_hours(
            combined_data['remaining_Ah'], combined_data['Total_Voltage'])
        combined_data['remaining_time'] = data_processor.calculate_remaining_time(
            combined_data['remaining_Ah'], shunt_current)

        # Write to CSV
        self.append_to_csv(filename, combined_data)

        # Clear the buffer and reset flush time
        self.data_buffer.clear()
        self.last_flush_time = time.time()

        return combined_data

    def append_to_csv(self, filename, data):
        """
        Appends a single row of data to the specified CSV file.
        """
        row = [data.get(header, '') for header in self.csv_headers]
        with open(filename, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(row)

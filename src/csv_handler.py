# csv_handler.py

import csv
import os
import threading
import logging

class CSVHandler:
    def __init__(self, default_directory='csv_data'):
        """
        Initializes the CSVHandler with a default save directory.
        """
        self.lock = threading.Lock()
        self.default_directory = default_directory
        self.ensure_directory_exists(self.default_directory)
        self.current_csv_file = os.path.join(self.default_directory, "telemetry_data.csv")
        self.secondary_csv_file = os.path.join(self.default_directory, "raw_hex_data.csv")
        self.logger = logging.getLogger(__name__)

    def ensure_directory_exists(self, directory):
        """
        Ensures that the specified directory exists; creates it if it doesn't.
        """
        if not os.path.exists(directory):
            os.makedirs(directory)
            self.logger.info(f"Created directory for CSV files: {directory}")

    def setup_csv(self, csv_file, headers):
        """
        Sets up the CSV file with headers if it doesn't exist.

        :param csv_file: Path to the CSV file.
        :param headers: List of header strings.
        """
        if not os.path.exists(csv_file):
            try:
                with open(csv_file, 'w', newline='') as file:
                    writer = csv.DictWriter(file, fieldnames=headers)
                    writer.writeheader()
                self.logger.info(f"CSV file created with headers: {csv_file}")
            except Exception as e:
                self.logger.error(f"Error setting up CSV file {csv_file}: {e}")

    def set_csv_save_directory(self, directory):
        """
        Sets a new directory for saving CSV files.

        :param directory: New directory path.
        """
        self.ensure_directory_exists(directory)
        self.default_directory = directory
        self.current_csv_file = os.path.join(self.default_directory, "telemetry_data.csv")
        self.secondary_csv_file = os.path.join(self.default_directory, "raw_hex_data.csv")
        self.logger.info(f"CSV save directory set to: {directory}")

    def get_csv_file_path(self):
        """
        Returns the current primary CSV file path.
        """
        return self.current_csv_file

    def get_secondary_csv_file_path(self):
        """
        Returns the current secondary CSV file path.
        """
        return self.secondary_csv_file

    def append_to_csv(self, csv_file, data):
        """
        Appends a single row of data to the specified CSV file without rewriting headers.

        :param csv_file: Path to the CSV file.
        :param data: Dictionary containing the data to append.
        """
        with self.lock:
            try:
                if not isinstance(data, dict):
                    self.logger.error(f"Data to append is not a dict: {data} (type: {type(data)})")
                    return  # Early exit to prevent further errors

                # Determine fieldnames from existing headers
                if os.path.exists(csv_file):
                    with open(csv_file, 'r', newline='') as read_file:
                        reader = csv.DictReader(read_file)
                        fieldnames = reader.fieldnames
                else:
                    # If file doesn't exist, use keys from data
                    fieldnames = data.keys()
                    self.logger.warning(f"CSV file {csv_file} does not exist. Using data keys as headers.")

                with open(csv_file, 'a', newline='') as file:
                    writer = csv.DictWriter(file, fieldnames=fieldnames)
                    # Ensure all keys in data match the fieldnames
                    row = {key: data.get(key, "") for key in fieldnames}
                    writer.writerow(row)
                self.logger.debug(f"Data appended to CSV: {csv_file}, Data: {row}")
            except Exception as e:
                self.logger.error(f"Error appending to CSV {csv_file}: {e}")

    def finalize_csv(self, original_csv, new_csv_path):
        """
        Finalizes the CSV by renaming it to a new path.

        :param original_csv: The original CSV file path.
        :param new_csv_path: The new CSV file path.
        """
        try:
            os.rename(original_csv, new_csv_path)
            self.logger.info(f"CSV file renamed to: {new_csv_path}")
        except Exception as e:
            self.logger.error(f"Error finalizing CSV file from {original_csv} to {new_csv_path}: {e}")

    def generate_csv_headers(self):
        """
        Generates CSV headers based on telemetry fields and battery information.

        :return: List of header strings.
        """
        telemetry_headers = [
            "MC1BUS_Voltage", "MC1BUS_Current", "MC1VEL_RPM", "MC1VEL_Velocity", "MC1VEL_Speed",
            "MC2BUS_Voltage", "MC2BUS_Current", "MC2VEL_Velocity", "MC2VEL_RPM", "MC2VEL_Speed",
            "DC_DRV_Motor_Velocity_setpoint", "DC_DRV_Motor_Current_setpoint", "DC_SWC_Position", "DC_SWC_Value",
            "BP_VMX_ID", "BP_VMX_Voltage", "BP_VMN_ID", "BP_VMN_Voltage", "BP_TMX_ID", "BP_TMX_Temperature",
            "BP_ISH_SOC", "BP_ISH_Amps", "BP_PVS_Voltage", "BP_PVS_milliamp/s", "BP_PVS_Ah",
            "MC1LIM_CAN Receive Error Count", "MC1LIM_CAN Transmit Error Count",
            "MC1LIM_Active Motor Info", "MC1LIM_Errors", "MC1LIM_Limits",
            "MC2LIM_CAN Receive Error Count", "MC2LIM_CAN Transmit Error Count",
            "MC2LIM_Active Motor Info", "MC2LIM_Errors", "MC2LIM_Limits"
        ]

        # Add additional calculated fields
        battery_headers = [
            "Total_Capacity_Wh", "Total_Capacity_Ah", "Total_Voltage",
            "Shunt_Remaining_Ah", "Used_Ah_Remaining_Ah", "Shunt_Remaining_wh",
            "Used_Ah_Remaining_wh", "Shunt_Remaining_Time", "Used_Ah_Remaining_Time",
            "Remaining_Capacity_Ah"
        ]

        # Add timestamp fields
        timestamp_headers = ["timestamp", "device_timestamp"]

        headers = timestamp_headers + telemetry_headers + battery_headers
        self.logger.debug(f"CSV headers generated: {headers}")
        return headers
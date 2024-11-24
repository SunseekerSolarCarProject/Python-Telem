# csv_handler.py

import csv
import os
import threading
import logging
from key_name_definitions import TelemetryKey, KEY_UNITS  # Import TelemetryKey enum and KEY_UNITS

class CSVHandler:
    def __init__(self, root_directory='.'):
        """
        Initializes the CSVHandler with a root directory for default files.
        """
        self.lock = threading.Lock()
        self.root_directory = os.path.abspath(root_directory)
        self.ensure_directory_exists(self.root_directory)
        
        # Define CSV file paths
        self.primary_csv_file = os.path.join(self.root_directory, "telemetry_data.csv")
        self.secondary_csv_file = os.path.join(self.root_directory, "raw_hex_data.csv")
        
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)  # Set to DEBUG for detailed logs

        # Define headers using TelemetryKey enum
        self.primary_headers = self.generate_primary_headers()
        self.secondary_headers = self.generate_secondary_headers()

        # Ensure the default CSV files exist with correct headers
        self.setup_csv(self.primary_csv_file, self.primary_headers)
        self.setup_csv(self.secondary_csv_file, self.secondary_headers)

    def ensure_directory_exists(self, directory):
        """
        Ensures the specified directory exists; creates it if it doesn't.
        """
        if not os.path.exists(directory):
            os.makedirs(directory)
            self.logger.info(f"Created directory: {directory}")

    def generate_primary_headers(self):
        """
        Generates primary CSV headers based on telemetry keys.

        :return: List of primary CSV headers.
        """
        # Define the desired order of telemetry keys
        ordered_keys = [
            TelemetryKey.TIMESTAMP.value[0], TelemetryKey.DEVICE_TIMESTAMP.value[0],
            TelemetryKey.MC1BUS_VOLTAGE.value[0], TelemetryKey.MC1BUS_CURRENT.value[0],
            TelemetryKey.MC1VEL_RPM.value[0], TelemetryKey.MC1VEL_VELOCITY.value[0], TelemetryKey.MC1VEL_SPEED.value[0],
            TelemetryKey.MC2BUS_VOLTAGE.value[0], TelemetryKey.MC2BUS_CURRENT.value[0],
            TelemetryKey.MC2VEL_VELOCITY.value[0], TelemetryKey.MC2VEL_RPM.value[0], TelemetryKey.MC2VEL_SPEED.value[0],
            TelemetryKey.DC_DRV_MOTOR_VELOCITY_SETPOINT.value[0], TelemetryKey.DC_DRV_MOTOR_CURRENT_SETPOINT.value[0],
            TelemetryKey.DC_SWITCH_POSITION.value[0], TelemetryKey.DC_SWC_VALUE.value[0],
            TelemetryKey.BP_VMX_ID.value[0], TelemetryKey.BP_VMX_VOLTAGE.value[0],
            TelemetryKey.BP_VMN_ID.value[0], TelemetryKey.BP_VMN_VOLTAGE.value[0],
            TelemetryKey.BP_TMX_ID.value[0], TelemetryKey.BP_TMX_TEMPERATURE.value[0],
            TelemetryKey.BP_ISH_SOC.value[0], TelemetryKey.BP_ISH_AMPS.value[0],
            TelemetryKey.BP_PVS_VOLTAGE.value[0], TelemetryKey.BP_PVS_MILLIAMP_S.value[0], TelemetryKey.BP_PVS_AH.value[0],
            TelemetryKey.MC1LIM_CAN_RECEIVE_ERROR_COUNT.value[0],
            TelemetryKey.MC1LIM_CAN_TRANSMIT_ERROR_COUNT.value[0],
            TelemetryKey.MC1LIM_ACTIVE_MOTOR_INFO.value[0], TelemetryKey.MC1LIM_ERRORS.value[0], TelemetryKey.MC1LIM_LIMITS.value[0],
            TelemetryKey.MC2LIM_CAN_RECEIVE_ERROR_COUNT.value[0],
            TelemetryKey.MC2LIM_CAN_TRANSMIT_ERROR_COUNT.value[0],
            TelemetryKey.MC2LIM_ACTIVE_MOTOR_INFO.value[0], TelemetryKey.MC2LIM_ERRORS.value[0], TelemetryKey.MC2LIM_LIMITS.value[0],
            TelemetryKey.TOTAL_CAPACITY_WH.value[0], TelemetryKey.TOTAL_CAPACITY_AH.value[0], TelemetryKey.TOTAL_VOLTAGE.value[0],
            TelemetryKey.SHUNT_REMAINING_AH.value[0], TelemetryKey.USED_AH_REMAINING_AH.value[0],
            TelemetryKey.SHUNT_REMAINING_WH.value[0], TelemetryKey.USED_AH_REMAINING_WH.value[0],
            TelemetryKey.SHUNT_REMAINING_TIME.value[0], TelemetryKey.USED_AH_REMAINING_TIME.value[0],
            TelemetryKey.REMAINING_CAPACITY_AH.value[0]
        ]
        self.logger.debug(f"Primary headers generated: {ordered_keys}")
        return ordered_keys

    def generate_secondary_headers(self):
        """
        Generates secondary CSV headers.

        :return: List of secondary CSV headers.
        """
        return ["timestamp", "raw_data"]

    def setup_csv(self, csv_file, headers):
        """
        Sets up a CSV file with headers if it doesn't exist.

        :param csv_file: Path to the CSV file.
        :param headers: List of header strings.
        """
        with self.lock:
            if not os.path.exists(csv_file):
                try:
                    with open(csv_file, 'w', newline='') as file:
                        writer = csv.DictWriter(file, fieldnames=headers)
                        writer.writeheader()
                    self.logger.info(f"CSV file created: {csv_file}")
                except Exception as e:
                    self.logger.error(f"Error setting up CSV file {csv_file}: {e}")

    def append_to_csv(self, csv_file, data):
        """
        Appends a row of data to the specified CSV file.

        :param csv_file: Path to the CSV file.
        :param data: Dictionary containing data to write.
        """
        try:
            if csv_file == self.primary_csv_file:
                headers = self.primary_headers
            elif csv_file == self.secondary_csv_file:
                headers = self.secondary_headers
            else:
                # If unknown CSV file, infer headers from data keys
                headers = list(data.keys())
                self.setup_csv(csv_file, headers)

            # Sanitize the data dictionary
            sanitized_data = {key: data.get(key, "N/A") for key in headers}

            with self.lock:
                if not os.path.exists(csv_file):
                    self.logger.warning(f"CSV file {csv_file} does not exist. Setting up with headers.")
                    self.setup_csv(csv_file, headers)

                with open(csv_file, 'a', newline='') as file:
                    writer = csv.DictWriter(file, fieldnames=headers)
                    writer.writerow(sanitized_data)
                self.logger.debug(f"Appended data to {csv_file}: {sanitized_data}")
        except Exception as e:
            self.logger.error(f"Error appending to CSV {csv_file}: {e}")

    def set_csv_save_directory(self, directory):
        """
        Sets a new directory for saving CSV files.

        :param directory: New directory path.
        """
        self.ensure_directory_exists(directory)
        self.change_csv_file_name("telemetry_data.csv", is_primary=True)
        self.change_csv_file_name("raw_hex_data.csv", is_primary=False)

    def change_csv_file_name(self, new_filename, is_primary):
        """
        Changes the CSV file name and updates the corresponding path.

        :param new_filename: New filename for the CSV.
        :param is_primary: Boolean indicating if it's the primary CSV.
        """
        file_path = os.path.join(self.root_directory, new_filename)
        headers = self.primary_headers if is_primary else self.secondary_headers
        self.setup_csv(file_path, headers)
        if is_primary:
            self.primary_csv_file = file_path
        else:
            self.secondary_csv_file = file_path
        self.logger.info(f"CSV file path updated: {file_path}")

    def get_csv_file_path(self):
        """
        Returns the current primary CSV file path.
        """
        return self.primary_csv_file

    def get_secondary_csv_file_path(self):
        """
        Returns the current secondary CSV file path.
        """
        return self.secondary_csv_file

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

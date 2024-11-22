# csv_handler.py

import csv
import os
import threading
import logging

class CSVHandler:
    def __init__(self, root_directory='.'):
        """
        Initializes the CSVHandler with a root directory for default files.
        """
        self.lock = threading.Lock()
        self.root_directory = os.path.abspath(root_directory)
        self.ensure_directory_exists(self.root_directory)
        self.primary_csv_file = os.path.join(self.root_directory, "telemetry_data.csv")
        self.secondary_csv_file = os.path.join(self.root_directory, "raw_hex_data.csv")
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)  # Set to DEBUG for detailed logs

        # Define primary and secondary headers
        self.primary_headers = [
            "timestamp", "device_timestamp", "MC1BUS_Voltage", "MC1BUS_Current", "MC1VEL_RPM",
            "MC1VEL_Velocity", "MC1VEL_Speed", "MC2BUS_Voltage", "MC2BUS_Current", "MC2VEL_Velocity",
            "MC2VEL_RPM", "MC2VEL_Speed", "DC_DRV_Motor_Velocity_setpoint", "DC_DRV_Motor_Current_setpoint",
            "DC_SWC_Position", "DC_SWC_Value", "BP_VMX_ID", "BP_VMX_Voltage", "BP_VMN_ID",
            "BP_VMN_Voltage", "BP_TMX_ID", "BP_TMX_Temperature", "BP_ISH_SOC", "BP_ISH_Amps",
            "BP_PVS_Voltage", "BP_PVS_milliamp/s", "BP_PVS_Ah", "MC1LIM_CAN Receive Error Count",
            "MC1LIM_CAN Transmit Error Count", "MC1LIM_Active Motor Info", "MC1LIM_Errors",
            "MC1LIM_Limits", "MC2LIM_CAN Receive Error Count", "MC2LIM_CAN Transmit Error Count",
            "MC2LIM_Active Motor Info", "MC2LIM_Errors", "MC2LIM_Limits",
            "Total_Capacity_Wh", "Total_Capacity_Ah", "Total_Voltage",
            "Shunt_Remaining_Ah", "Used_Ah_Remaining_Ah", "Shunt_Remaining_wh",
            "Used_Ah_Remaining_wh", "Shunt_Remaining_Time", "Used_Ah_Remaining_Time",
            "Remaining_Capacity_Ah"
        ]

        self.secondary_headers = ["timestamp", "raw_data"]

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

    def setup_csv(self, csv_file, headers):
        """
        Sets up a CSV file with headers if it doesn't exist.
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

    def generate_csv_headers(self):
        """
        Generates CSV headers based on telemetry fields and battery information.

        :return: List of header strings.
        """
        telemetry_headers = [
            "MC1BUS_Voltage", "MC1BUS_Current", "MC1VEL_RPM", "MC1VEL_Velocity", "MC1VEL_Speed",
            "MC2BUS_Voltage", "MC2BUS_Current", "MC2VEL_Velocity", "MC2VEL_RPM", "MC2VEL_Speed",
            "DC_DRV_Motor_Velocity_setpoint", "DC_DRV_Motor_Current_setpoint", "DC_SWC_Position", "DC_SWC_Value",
            "BP_VMX_ID", "BP_VMX_Voltage", "BP_VMN_ID",
            "BP_VMN_Voltage", "BP_TMX_ID", "BP_TMX_Temperature",
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

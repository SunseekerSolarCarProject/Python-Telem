# csv_handler.py

import csv
import os
import logging

class CSVHandler:
    def __init__(self, default_directory='csv_data'):
        """
        Initializes the CSVHandler with a default save directory.
        """
        self.default_directory = default_directory
        self.ensure_directory_exists(self.default_directory)
        self.current_csv_file = os.path.join(self.default_directory, "telemetry_data.csv")
        self.logger = logging.getLogger(__name__)

    def ensure_directory_exists(self, directory):
        """
        Ensures that the specified directory exists; creates it if it doesn't.
        """
        if not os.path.exists(directory):
            os.makedirs(directory)
            self.logger.info(f"Created directory for CSV files: {directory}")

    def setup_csv(self, filename, headers):
        """
        Initialize a CSV file with headers.
        """
        try:
            with open(filename, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(headers)
            self.logger.info(f"CSV file '{filename}' initialized with headers.")
        except Exception as e:
            self.logger.error(f"Error setting up CSV file '{filename}': {e}")

    def set_csv_save_directory(self, directory):
        """
        Sets a new directory for saving CSV files.
        """
        self.ensure_directory_exists(directory)
        self.default_directory = directory
        self.current_csv_file = os.path.join(self.default_directory, "telemetry_data.csv")
        self.logger.info(f"CSV save directory set to: {directory}")

    def get_csv_file_path(self):
        """
        Returns the current CSV file path.
        """
        return self.current_csv_file
    
    def append_to_csv(self, filename, headers, data):
        """
        Append a single row of data to the specified CSV file.
        """
        row = [data.get(header, '') for header in headers]
        try:
            with open(filename, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(row)
            self.logger.debug(f"Appended row to CSV file {filename}: {row}")
        except Exception as e:
            self.logger.error(f"Error appending row to CSV file '{filename}': {e}")

    def finalize_csv(self, original_file, new_file):
        """
        Copy the content of the original CSV to a new file with a custom name.
        """
        try:
            with open(original_file, 'r') as original, open(new_file, 'w', newline='') as new_file_obj:
                new_file_obj.write(original.read())
            self.logger.info(f"Data successfully saved to {new_file}.")
        except Exception as e:
            self.logger.error(f"Error finalizing CSV file: {e}")

    def generate_csv_headers(self):
        """
        Generate a list of headers for the CSV file based on telemetry fields and battery information.
        """
        telemetry_headers = [
            "MC1BUS_Voltage", "MC1BUS_Current", "MC1VEL_RPM", "MC1VEL_Velocity", "MC1VEL_Speed",
            "MC2BUS_Voltage", "MC2BUS_Current", "MC2VEL_Velocity", "MC2VEL_RPM", "MC2VEL_Speed",
            "DC_DRV_Motor_Velocity_setpoint", "DC_DRV_Motor_Current_setpoint", "DC_SWC_Position", "DC_SWC_Value",
            "BP_VMX_ID", "BP_VMX_Voltage", "BP_VMN_ID", "BP_VMN_Voltage", "BP_TMX_ID", "BP_TMX_Temperature",
            "BP_ISH_SOC", "BP_ISH_Amps", "BP_PVS_Voltage", "BP_PVS_milliamp/s", "BP_PVS_Ah",
            "MC1LIM", "MC2LIM"
        ]

        # Add additional calculated fields
        battery_headers = [
            "Total_Capacity_Wh", "Total_Capacity_Ah", "Total_Voltage",
            "Shunt_Remaining_Ah", "Used_Ah_Remaining_Ah", "Shunt_Remaining_wh",
            "Used_Ah_Remaining_wh", "Shunt_Remaining_Time", "Used_Ah_Remaining_Time"
        ]

        # Add timestamp fields
        timestamp_headers = ["timestamp", "device_timestamp"]

        headers = timestamp_headers + telemetry_headers + battery_headers
        self.logger.debug(f"CSV headers generated: {headers}")
        return headers

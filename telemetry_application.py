# telemetry_application.py

import time
import csv
import serial
import serial.tools.list_ports
from datetime import datetime
from serial_reader import SerialReaderThread
from data_processor import DataProcessor

# Updated units and key descriptions
units = {
    'DC_DRV_Motor_Velocity_setpoint': '#',
    'DC_DRV_Motor_Currrent_setpoint': '#',
    'DC_SWC_Position': ' ',
    'DC_SWC_Value1': '#',
    'MC1BUS_Voltage': 'V',
    'MC1BUS_Current': 'A',
    'MC2BUS_Voltage': 'V',
    'MC2BUS_Current': 'A',
    'MC1VEL_Velocity': 'M/s',
    'MC1VEL_Speed': 'Mph',
    'MC1VEL_RPM': 'RPM',
    'MC2VEL_Velocity': 'M/s',
    'MC2VEL_Speed': 'Mph',
    'MC2VEL_RPM': 'RPM',
    'BP_VMX_ID': '#',
    'BP_VMX_Voltage': 'V',
    'BP_VMN_ID': '#',
    'BP_VMN_Voltage': 'V',
    'BP_TMX_ID': '#',
    'BP_TMX_Temperature': '°F',
    'BP_PVS_Voltage': 'V',
    'BP_PVS_milliamp/s': 'mA/s',
    'BP_PVS_Ah': 'Ah',
    'BP_ISH_Amps': 'A',
    'BP_ISH_SOC': '%'
}

class TelemetryApplication:
    def __init__(self, baudrate, buffer_timeout=2.0, buffer_size=20):
        self.baudrate = baudrate
        self.serial_reader_thread = None
        self.data_processor = DataProcessor()
        self.battery_info = self.get_user_battery_input()
        self.csv_headers = self.generate_csv_headers()
        self.csv_file = "telemetry_data.csv"
        self.secondary_csv_headers = ["timestamp", "raw_data"]
        self.secondary_csv_file = "raw_hex_data.csv"
        self.used_Ah = 0.0
        self.buffer_timeout = buffer_timeout  # Time in seconds to flush buffer
        self.buffer_size = buffer_size  # Max number of data points before flushing
        self.data_buffer = []  # Initialize buffer
        self.last_flush_time = time.time()  # Track last flush timestampe
        self.setup_csv(self.csv_file, self.csv_headers)
        self.setup_csv(self.secondary_csv_file, self.secondary_csv_headers)

    def get_user_battery_input(self):
        print("Please enter the following battery information:")
        capacity_ah = float(input("Battery Capacity (Ah) per cell: "))
        voltage = float(input("Battery Voltage (V) per cell: "))
        quantity = int(input("Number of cells: "))
        series_strings = int(input("Number of series strings: "))

        battery_info = self.data_processor.calculate_battery_capacity(capacity_ah, voltage, quantity, series_strings)
        if 'error' in battery_info:
            print(f"Error calculating battery info: {battery_info['error']}")
            return None
        return battery_info

    def generate_csv_headers(self):
        """
        Define all potential CSV columns based on known telemetry fields and battery info.
        """
        telemetry_headers = [
            "MC1BUS_Voltage", "MC1BUS_Current", "MC1VEL_RPM", "MC1VEL_Velocity", "MC1VEL_Speed",
            "MC2BUS_Voltage", "MC2BUS_Current", "MC2VEL_Velocity", "MC2VEL_RPM", "MC2VEL_Speed",
            "DC_DRV_Motor_Velocity_setpoint", "DC_DRV_Motor_Current_setpoint", "DC_SWC", "BP_VMX_ID",
            "BP_VMX_Voltage", "BP_VMN_ID", "BP_VMN_Voltage", "BP_TMX_ID", "BP_TMX_Temperature",
            "BP_ISH_SOC", "BP_ISH_Amps", "BP_PVS_Voltage", "BP_PVS_milliamp/s", "BP_PVS_Ah"
        ]
        
        # Add additional calculated fields
        battery_headers = ["total_capacity_wh", "total_capacity_ah", "total_voltage", 
                           "remaining_Ah", "remaining_wh", "remaining_time"]
        
        # Add timestamp fields
        timestamp_headers = ["timestamp", "device_timestamp"]

        return timestamp_headers + telemetry_headers + battery_headers

    def setup_csv(self):
        with open(self.csv_file, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(self.csv_headers)

    def select_port(self):
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            print("No serial ports found.")
            return None
        print("Available ports:")
        for i, port in enumerate(ports):
            print(f"{i}: {port.device}")
        choice = int(input("Select port number: "))
        return ports[choice].device if 0 <= choice < len(ports) else None
    
    def start(self):
        port = self.select_port()
        if not port:
            print("Invalid port selection.")
            return

        self.serial_reader_thread = SerialReaderThread(port, self.baudrate, process_data_callback=self.process_data,
        process_raw_data_callback=self.process_raw_data)  # New callback for raw data
        self.serial_reader_thread.start()
        print(f"Telemetry application started on {port}.")

        try:
            while True:
                time.sleep(0.05)
        except KeyboardInterrupt:
            print("Shutting down.")
        finally:
            if self.serial_reader_thread:
                self.serial_reader_thread.stop()
                self.serial_reader_thread.join()
            self.finalize_csv()
            print("Application stopped.")

    def process_data(self, data):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if data.startswith("TL_TIM"):
            device_timestamp = data.split(",")[1].strip()  # Extract time value after comma
            self.data_buffer.append({"device_timestamp": device_timestamp})
            return
        
        # Parse other telemetry data lines
        processed_data = self.data_processor.parse_data(data)
        if processed_data:
            processed_data['timestamp'] = timestamp  # Add local timestamp
            self.data_buffer.append(processed_data)

            # Flush buffer if timeout or size reached
            if len(self.data_buffer) >= self.buffer_size or \
                    (time.time() - self.last_flush_time) >= self.buffer_timeout:
                self.flush_buffer()

    def process_raw_data(self, raw_data):
        """
        Logs the raw hex data directly to the secondary CSV with a timestamp.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.append_to_csv(self.secondary_csv_file, {"timestamp": timestamp, "raw_data": raw_data}, self.secondary_csv_headers)

    def flush_buffer(self):
        """
        Displays and saves buffered data, then clears the buffer.
        """
        if not self.data_buffer:
            return

        # Combine data from buffer into a single dictionary
        combined_data = {}
        for data in self.data_buffer:
            combined_data.update(data)

        # Check if the combined_data contains all required keys
        if not self.is_buffer_complete(combined_data):
            # If incomplete, wait for more data to accumulate in buffer
            return

        # Ensure both timestamps are present
        combined_data['timestamp'] = combined_data.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        combined_data['device_timestamp'] = combined_data.get('device_timestamp', 'N/A')

        # Calculate and add battery metrics to combined_data
        shunt_current = combined_data.get('BP_ISH_Amps', 0)
        combined_data['total_capacity_wh'] = self.battery_info.get('total_capacity_wh', 0.0)
        combined_data['total_capacity_ah'] = self.battery_info.get('total_capacity_ah', 0.0)
        combined_data['total_voltage'] = self.battery_info.get('total_voltage', 0.0)

        # Calculate remaining metrics
        remaining_Ah = self.data_processor.calculate_remaining_capacity(
            self.used_Ah, combined_data['total_capacity_ah'], shunt_current, 1)
        remaining_time = self.data_processor.calculate_remaining_time(remaining_Ah, shunt_current)
        remaining_wh = self.data_processor.calculate_watt_hours(remaining_Ah, combined_data['total_voltage'])

        # Add remaining metrics to combined_data
        combined_data['remaining_Ah'] = remaining_Ah
        combined_data['remaining_wh'] = remaining_wh
        combined_data['remaining_time'] = remaining_time

        # Display and save the complete data set
        self.display_data(combined_data, self.battery_info, self.used_Ah, shunt_current, combined_data['device_timestamp'])
        self.append_to_csv(combined_data)

        # Clear buffer and reset flush timer
        self.data_buffer.clear()
        self.last_flush_time = time.time()

    def display_data(self, data, battery_info, used_Ah, shunt_current, device_timestamp):
        """
        Display battery, telemetry, and timestamp data in a structured format.
        """
        ordered_keys = [
        "total_capacity_wh", "total_capacity_ah", "total_voltage",
        "MC1BUS_Voltage", "MC1BUS_Current",
        "MC1VEL_RPM", "MC1VEL_Velocity", "MC1VEL_Speed",
        "MC2BUS_Voltage", "MC2BUS_Current",
        "MC2VEL_Velocity", "MC2VEL_RPM", "MC2VEL_Speed",
        "DC_DRV_Motor_Velocity_setpoint", "DC_DRV_Motor_Current_setpoint",
        "DC_SWC_Position", "DC_SWC_Value1", 
        "BP_VMX_ID", "BP_VMX_Voltage",
        "BP_VMN_ID", "BP_VMN_Voltage",
        "BP_TMX_ID", "BP_TMX_Temperature",
        "BP_ISH_SOC", "BP_ISH_Amps",
        "BP_PVS_Voltage", "BP_PVS_milliamp/s", "BP_PVS_Ah",
        "MC1LIM Motor Controller Data"
        "MC2LIM Motor Controller Data"
        ]
        
        # Display battery capacity at the top
        print(f"total_capacity_wh: {battery_info.get('total_capacity_wh', 0.0):.2f}")
        print(f"total_capacity_ah: {battery_info.get('total_capacity_ah', 0.0):.2f}")
        print(f"total_voltage: {battery_info.get('total_voltage', 0.0):.2f}")

        # Display telemetry data in an organized format
        for key in ordered_keys:
            if key == "DC_SWC_Position":
                # Interpret DC_SWC_Position from its hex value to a descriptive string
                swc_hex_value = data.get("DC_SWC_Position", "0x00000000")
                swc_description = self.data_processor.steering_wheel_desc.get(swc_hex_value, "unknown")
                print(f"{key}: {swc_description} ({swc_hex_value})")

            elif key == "DC_SWC_Value1":
                # Show bit value directly for DC_SWC_Value1
                swc_bit_value = data.get("DC_SWC_Value1", "N/A")
                print(f"{key}: {swc_bit_value} #")

            elif key == "MC1LIM Motor Controller Data":
                # Special handling for the MC1LIM motor controller data
                motor_data = data.get("MC1LIM Motor Controller Data", {})
                if motor_data:
                    print("\nMC1LIM Motor Controller Data:")
                    print(f"  CAN Receive Error Count: {motor_data.get('CAN Receive Error Count', 'N/A')}")
                    print(f"  CAN Transmit Error Count: {motor_data.get('CAN Transmit Error Count', 'N/A')}")
                    print(f"  Active Motor Info: {motor_data.get('Active Motor Info', 'N/A')}")
                    print(f"  Errors: {', '.join(motor_data.get('Errors', [])) if motor_data.get('Errors') else 'None'}")
            elif key == "MC2LIM Motor Controller Data":
                # Special handling for the MC2LIM motor controller data
                motor_data = data.get("MC2LIM Motor Controller Data", {})
                if motor_data:
                    print("\nMC1LIM Motor Controller Data:")
                    print(f"  CAN Receive Error Count: {motor_data.get('CAN Receive Error Count', 'N/A')}")
                    print(f"  CAN Transmit Error Count: {motor_data.get('CAN Transmit Error Count', 'N/A')}")
                    print(f"  Active Motor Info: {motor_data.get('Active Motor Info', 'N/A')}")
                    print(f"  Errors: {', '.join(motor_data.get('Errors', [])) if motor_data.get('Errors') else 'None'}")
                    print(f"  Limits: {', '.join(motor_data.get('Limits', [])) if motor_data.get('Limits') else 'None'}")
                    print(f"  Limits: {', '.join(motor_data.get('Limits', [])) if motor_data.get('Limits') else 'None'}")
            else:
                # General handling for other fields
                value = data.get(key, "N/A")
                unit = units.get(key, '')
                if isinstance(value, (int, float)):
                    print(f"{key}: {value:.2f} {unit}")
                else:
                    print(f"{key}: {value} {unit}")

        # Display remaining battery information and timestamps at the bottom
        if 'total_capacity_ah' in battery_info and 'total_voltage' in battery_info:
            remaining_Ah = self.data_processor.calculate_remaining_capacity(
                used_Ah, battery_info['total_capacity_ah'], shunt_current, 1)
            remaining_time = self.data_processor.calculate_remaining_time(remaining_Ah, shunt_current)
            remaining_wh = self.data_processor.calculate_watt_hours(remaining_Ah, battery_info['total_voltage'])

            print(f"Remaining Capacity (Ah): {remaining_Ah:.2f}")
            print(f"Remaining Capacity (Wh): {remaining_wh:.2f}")
            print(f"Remaining Time (hours): {remaining_time if remaining_time != float('inf') else 'inf'}")

        # Display timestamps at the end
        print(f"Device Timestamp: {device_timestamp}")
        print(f"System Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 40)


    def append_to_csv(self, combined_data):
        """
        Appends a structured row to the CSV with all available data.
        """
        row = [combined_data.get(header, '') for header in self.csv_headers]  # Fill row based on headers

        with open(self.csv_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(row)

    def finalize_csv(self):
        custom_filename = input("Enter a filename to save the CSV data (without extension): ")
        custom_filename = f"{custom_filename}.csv"
        with open(self.csv_file, 'r') as original, open(custom_filename, 'w', newline='') as new_file:
            new_file.write(original.read())
        print(f"Data successfully saved to {custom_filename}.")

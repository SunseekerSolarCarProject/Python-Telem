# telemetry_application.py

import time
import csv
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
    def __init__(self, baudrate):
        self.baudrate = baudrate
        self.serial_reader_thread = None
        self.data_processor = DataProcessor()
        self.battery_info = self.get_user_battery_input()
        self.csv_file = "telemetry_data.csv"
        self.used_Ah = 0.0
        self.setup_csv()

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

    def setup_csv(self):
        with open(self.csv_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Timestamp', 'Data'])

    def start(self):
        port = self.select_port()
        if not port:
            print("Invalid port selection.")
            return

        self.serial_reader_thread = SerialReaderThread(port, self.baudrate, self.process_data)
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
        processed_data = self.data_processor.parse_data(data)
        if processed_data:
            shunt_current = processed_data.get('BP_ISH_Amps', 0)
            self.display_data(processed_data, self.battery_info, self.used_Ah, shunt_current)
            self.append_to_csv(timestamp, processed_data)

    def display_data(self, data, battery_info, used_Ah, shunt_current):
        """
        Display the data, converting float values and adding units.
        """
        for key, value in data.items():
            if key not in ['timestamp', 'system_time']:
                if key == 'DC_SWC':
                    swc_description = value.get("SWC_States", "Unknown")
                    print(f"{key}: {swc_description}")
                elif isinstance(value, dict):
                    print(f"\n{key} Motor Controller Data:")
                    print(f"  CAN Receive Error Count: {value.get('CAN Receive Error Count')}")
                    print(f"  CAN Transmit Error Count: {value.get('CAN Transmit Error Count')}")
                    print(f"  Active Motor Info: {value.get('Active Motor Info')}")
                    print(f"  Errors: {', '.join(value.get('Errors', [])) if value.get('Errors') else 'None'}")
                    print(f"  Limits: {', '.join(value.get('Limits', [])) if value.get('Limits') else 'None'}")
                else:
                    unit = units.get(key, '')
                    if isinstance(value, (int, float)):
                        print(f"{key}: {value:.2f} {unit}")
                    else:
                        print(f"{key}: {value} {unit}")

        # Display battery status
        remaining_Ah = self.data_processor.calculate_remaining_capacity(used_Ah, battery_info['total_capacity_ah'], shunt_current, 1)
        remaining_time = self.data_processor.calculate_remaining_time(remaining_Ah, shunt_current)
        remaining_wh = self.data_processor.calculate_watt_hours(remaining_Ah, battery_info['total_voltage'])
        
        print(f"Remaining Capacity (Ah): {remaining_Ah:.2f}")
        print(f"Remaining Capacity (Wh): {remaining_wh:.2f}")
        print(f"Remaining Time (hours): {remaining_time:.2f}")

        if 'device_timestamp' in data:
            print(f"Device Timestamp: {data['device_timestamp']}")
        if 'system_time' in data:
            print(f"System Time: {data['system_time']}")
        print("-" * 40)

    def append_to_csv(self, timestamp, data):
        with open(self.csv_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            for key, value in data.items():
                if isinstance(value, tuple):
                    writer.writerow([timestamp, f"{key}_1", value[0]])
                    writer.writerow([timestamp, f"{key}_2", value[1]])
                elif isinstance(value, list):
                    writer.writerow([timestamp, key, ', '.join(value)])
                else:
                    writer.writerow([timestamp, key, value])
                    
    def finalize_csv(self):
        custom_filename = input("Enter a filename to save the CSV data (without extension): ")
        custom_filename = f"{custom_filename}.csv"
        with open(self.csv_file, 'r') as original, open(custom_filename, 'w', newline='') as new_file:
            new_file.write(original.read())
        print(f"Data successfully saved to {custom_filename}.")

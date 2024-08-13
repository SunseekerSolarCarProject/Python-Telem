# filename: serial_data_processor_terminal.py

import struct
import serial
import serial.tools.list_ports
import time
import csv
from datetime import datetime
import random  # Import random for generating test data

units = {
    'MC1 Velocity': 'm/s',
    'MC2 Velocity': 'm/s',
    'MC1 Bus': 'A',
    'MC2 Bus': 'A',
    'BP_VMX': 'V',
    'BP_VMN': 'V',
    'BP_TMX': '°C',
    'BP_ISH': 'A',
    'BP_PVS': 'V',
    'Battery mAh': 'mAh'
}

def find_serial_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        return port.device
    return None

def configure_serial(port, baudrate=9600, timeout=1):
    try:
        ser = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
        if ser.isOpen():
            print(f"Serial port {port} opened successfully.")
        return ser
    except serial.SerialException as e:
        print(f"Error opening serial port {port}: {e}")
        return None

def hex_to_float(hex_data):
    try:
        if hex_data.startswith("0x"):
            hex_data = hex_data[2:]

        if "HHHHHHHH" in hex_data:
            return 0.0
        
        if len(hex_data) != 8:
            raise ValueError(f"Invalid hex length: {hex_data}")
        
        byte_data = bytes.fromhex(hex_data)
        float_value = struct.unpack('<f', byte_data)[0]  # Using '<f' for little-endian order
        
        if not (float('-inf') < float_value < float('inf')):
            raise ValueError(f"Unreasonable float value: {float_value}")
        
        return float_value
    except (ValueError, struct.error) as e:
        print(f"Error converting hex to float for data '{hex_data}': {e}")
        return 0.0

def process_serial_data(line):
    processed_data = {}
    parts = line.split(',')

    if parts[0] != 'TL_TIM':
        key = parts[0]
        hex1 = parts[1].strip()
        hex2 = parts[2].strip()
        float1 = hex_to_float(hex1)
        float2 = hex_to_float(hex2)
        
        processed_data[f"{key}_Value1"] = float1
        processed_data[f"{key}_Value2"] = float2
    
    return processed_data

def generate_random_data():
    """Generate random hex data for testing."""
    keys = ['MC1BUS', 'MC1VEL', 'MC2BUS', 'MC2VEL', 'BP_VMX', 'BP_VMN', 'BP_TMX', 'BP_ISH', 'BP_PVS']
    hex_lines = []
    for key in keys:
        # Generate two random IEEE 754 single-precision floats and convert them to hex
        value1 = struct.pack('<f', random.uniform(-1000, 1000)).hex()
        value2 = struct.pack('<f', random.uniform(-1000, 1000)).hex()
        hex_line = f"{key},0x{value1},0x{value2}"
        hex_lines.append(hex_line)
    return hex_lines

def read_and_process_data(data_list, ser=None):
    try:
        buffer = ""
        interval_data = {}
        while True:
            # Generate random data instead of reading from serial
            hex_lines = generate_random_data()
            for line in hex_lines:
                line = line.strip()
                processed_data = process_serial_data(line)
                if processed_data:
                    interval_data.update(processed_data)
            
            # Simulate a timestamp in TL_TIM format
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            interval_data['timestamp'] = timestamp
            data_list.append(interval_data.copy())
            display_data(interval_data)
            interval_data.clear()
            
            # Simulate a delay between data packets
            time.sleep(1)

    except KeyboardInterrupt:
        print("Stopping data generation due to KeyboardInterrupt.")
        raise  # Re-raise the KeyboardInterrupt to handle it in the main loop

def display_data(data):
    for key, value in data.items():
        if key != 'timestamp':
            print(f"{key}: {value:.2f} {units.get(key.split('_')[0], '')}")
    print(f"Timestamp: {data['timestamp']}")
    print("-" * 40)

def save_data_to_csv(data_list, filename):
    if not data_list:
        return
    
    keys = data_list[0].keys()
    with open(filename, 'w', newline='') as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(data_list)

def get_save_location():
    save_location = input("Enter the path to save the CSV (including file name) example: C:_Users_user_downloads_csv_serial_data.csv \n")
    if not save_location:
        save_location = 'serial_data.csv'
    return save_location

if __name__ == '__main__':
    data_list = []

    try:
        while True:
            port = find_serial_port()
            if port:
                serial_port = configure_serial(port)
                if serial_port:
                    try:
                        read_and_process_data(data_list, serial_port)
                    except KeyboardInterrupt:
                        print("Exiting program.")
                        raise  # Re-raise to handle in the outer try block
                else:
                    print("Failed to configure serial port. Retrying in 60 seconds...")
                    time.sleep(60)
            else:
                print("No serial port found. Generating test data...")
                try:
                    read_and_process_data(data_list)  # Generate test data instead of reading from serial
                except KeyboardInterrupt:
                    print("Exiting program.")
                    raise  # Re-raise to handle in the outer try block
    except KeyboardInterrupt:
        print("Program interrupted. Saving data...")
        save_location = get_save_location()
        save_data_to_csv(data_list, save_location)
        print(f"Data saved to {save_location}")
        print("Process terminated.")

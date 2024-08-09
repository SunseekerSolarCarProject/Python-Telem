# filename: serial_data_processor_terminal_with_random_data.py

import struct
import time
import csv
from datetime import datetime
import random

# Define the unit labels for each data point
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

def random_hex_float(low=-50, high=50):
    """
    Generate a random float within a range and convert it to a hex string.
    """
    float_val = random.uniform(low, high)
    hex_val = struct.pack('!f', float_val).hex()  # Convert the float to a hex string
    return f"0x{hex_val}"

def generate_random_data():
    """
    Generate random data in the expected format.
    """
    data = [
        f"MC1BUS,{random_hex_float(0, 100)},{random_hex_float(0, 100)}",
        f"MC1VEL,{random_hex_float(0, 100)},{random_hex_float(0, 100)}",
        f"MC2BUS,{random_hex_float(0, 100)},{random_hex_float(0, 100)}",
        f"MC2VEL,{random_hex_float(0, 100)},{random_hex_float(0, 100)}",
        f"BP_VMX,{random_hex_float(3, 4.2)},{random_hex_float(3, 4.2)}",  # Battery cell voltage range
        f"BP_VMN,{random_hex_float(3, 4.2)},{random_hex_float(3, 4.2)}",
        f"BP_TMX,{random_hex_float(20, 80)},{random_hex_float(20, 80)}",  # Temperature in Celsius
        f"BP_ISH,{random_hex_float(-100, 100)},{random_hex_float(-100, 100)}",  # Current can be negative
        f"BP_PVS,{random_hex_float(200, 400)},{random_hex_float(200, 400)}",  # Pack voltage range
    ]
    return data

def hex_to_float(hex_data):
    """
    Convert hex data to a single-precision float.

    :param hex_data: Hex string
    :return: Converted float value
    """
    try:
        if hex_data.startswith("0x"):
            hex_data = hex_data[2:]
        if "HHHHHHHH" in hex_data:
            return 0.0
        if len(hex_data) != 8:
            raise ValueError(f"Invalid hex length: {hex_data}")
        byte_data = bytes.fromhex(hex_data)
        float_value = struct.unpack('!f', byte_data)[0]
        return float_value
    except (ValueError, struct.error) as e:
        print(f"Error converting hex to float for data '{hex_data}': {e}")
        return None

def process_serial_data(line):
    """
    Process a single line of pseudo-random data (mimicking serial data).

    :param line: A line of serial data
    :return: Processed data as a dictionary
    """
    processed_data = {}
    parts = line.split(',')

    key = parts[0]
    hex1 = parts[1].strip()
    hex2 = parts[2].strip()
    float1 = hex_to_float(hex1)
    float2 = hex_to_float(hex2)
    processed_data[key] = (float1, float2)
    
    return processed_data

def read_and_process_data(data_list):
    """
    Simulate reading hex data by generating random data, convert it to float, and process it.

    :param data_list: List to store processed data
    """
    try:
        while True:
            time.sleep(1)  # Simulate delay between data reads
            data = generate_random_data()
            processed_data = {}
            for line in data:
                line = line.strip()
                if line and line not in ["ABCDEF", "UVWXYZ"]:
                    processed_line = process_serial_data(line)
                    processed_data.update(processed_line)

            timestamp = datetime.now().strftime('%H:%M:%S')
            processed_data['timestamp'] = timestamp

            # Add the processed data to the list
            data_list.append(processed_data)

            # Display the processed data
            display_data(processed_data)
    except KeyboardInterrupt:
        print("Stopping data simulation.")

def process_data_for_purpose(data):
    """
    Process the data for specific purposes and calculate the milliamp-hour.

    :param data: Dictionary of processed data
    :return: Dictionary of results
    """
    results = data.copy()  # Copy the original data
    
    if 'BP_ISH' in data and 'BP_PVS' in data:
        current_in_amps = data['BP_ISH'][0]
        voltage_in_volts = data['BP_PVS'][0]
        if current_in_amps is not None and voltage_in_volts is not None:
            results['Battery mAh'] = current_in_amps * voltage_in_volts * 1000
    
    return results

def display_data(data):
    """
    Display the processed data in the terminal.

    :param data: Dictionary of processed data
    """
    for key, value in data.items():
        if key != 'timestamp':
            print(f"{key}: {value} {units.get(key, '')}")
    if 'Battery mAh' in data:
        print(f"Battery mAh: {data['Battery mAh']} {units['Battery mAh']}")
    print(f"Timestamp: {data['timestamp']}")
    print("-" * 40)

def save_data_to_csv(data_list, filename):
    """
    Save the processed data to a CSV file.

    :param data_list: List of processed data
    :param filename: CSV file name
    """
    if not data_list:
        return
    
    keys = data_list[0].keys()
    with open(filename, 'w', newline='') as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(data_list)

def get_save_location():
    """
    Get the CSV save location from the user.

    :return: The file path to save the CSV file
    """
    save_location = input("Enter the path to save the CSV file (including file name): ")
    if not save_location:
        save_location = 'serial_data.csv'
    return save_location

if __name__ == '__main__':
    data_list = []
    
    try:
        read_and_process_data(data_list)
    except KeyboardInterrupt:
        save_location = get_save_location()
        save_data_to_csv(data_list, save_location)
        print(f"Data saved to {save_location}")
        print("Process terminated.")

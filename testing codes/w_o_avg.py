# filename: serial_data_processor_terminal.py

import struct
import serial
import serial.tools.list_ports
import time
import csv
from datetime import datetime

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
    """
    Convert a hex string representing IEEE 754 single-precision floating-point to a float.

    :param hex_data: A string containing the hex representation (e.g., '40490FDB')
    :return: The corresponding floating-point value, or 0.0 if the data is invalid
    """
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

def read_and_process_data(data_list, ser):
    try:
        buffer = ""
        interval_data = {}
        while True:
            if ser.inWaiting() > 0:
                buffer += ser.read(ser.inWaiting()).decode('utf-8')
                if '\n' in buffer:
                    lines = buffer.split('\n')
                    for line in lines[:-1]:
                        line = line.strip()
                        if line and line not in ["ABCDEF", "UVWXYZ"]:
                            processed_data = process_serial_data(line)
                            if processed_data:
                                interval_data.update(processed_data)
                    buffer = lines[-1]

                    if 'TL_TIM' in line:
                        timestamp = line.split(',')[1].strip()
                        interval_data['timestamp'] = timestamp
                        data_list.append(interval_data.copy())
                        display_data(interval_data)
                        interval_data.clear()

    except serial.SerialException as e:
        print(f"Serial exception: {e}")
    except KeyboardInterrupt:
        print("Stopping serial read due to KeyboardInterrupt.")
        raise  # Re-raise the KeyboardInterrupt to handle it in the main loop
    finally:
        if ser.isOpen():
            ser.close()
            print("Serial port closed.")

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
    save_location = input("Enter the path to save the CSV file (including file name): ")
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
                    connection_lost = False
                    while True:
                        try:
                            if not read_and_process_data(data_list, serial_port):
                                connection_lost = True
                                break  # Exit the inner loop to try reconnecting
                        except KeyboardInterrupt:
                            print("Exiting program.")
                            raise  # Re-raise to handle in the outer try block
                    if connection_lost:
                        continue  # Try reconnecting by going back to find_serial_port()
                else:
                    print("Failed to configure serial port. Retrying in 60 seconds...")
                    time.sleep(20)
            else:
                print("No serial port found. Retrying in 60 seconds...")
                time.sleep(20)
    except KeyboardInterrupt:
        print("Program interrupted. Saving data...")
        save_location = get_save_location()
        save_data_to_csv(data_list, save_location)
        print(f"Data saved to {save_location}")
        print("Process terminated.")

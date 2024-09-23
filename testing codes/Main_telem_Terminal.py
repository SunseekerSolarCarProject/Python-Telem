import struct
import serial
import serial.tools.list_ports
import time
import csv
from datetime import datetime

# Define units for the sensors
units = {
    'MC1BUS': 'A',
    'MC2BUS': 'A',
    'MC1VEL': 'm/s',
    'MC2VEL': 'm/s',
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
    Returns 0.0 if the hex string is invalid or contains 'HHHHHHHH'.
    """
    try:
        # Treat 'HHHHHHHH' or invalid data as zero
        if hex_data == 'HHHHHHHH':
            return 0.0

        # Remove the '0x' prefix if present
        if hex_data.startswith("0x"):
            hex_data = hex_data[2:]

        # Ensure the hex string is 8 characters long
        if len(hex_data) != 8:
            raise ValueError(f"Invalid hex length: {hex_data}")

        # Convert hex string to bytes
        byte_data = bytes.fromhex(hex_data)

        # Unpack to float using IEEE 754 format
        float_value = struct.unpack('<f', byte_data)[0]  # Use '<f' for little-endian order

        return float_value
    except (ValueError, struct.error):
        # Return 0.0 for any errors
        return 0.0

def process_serial_data(line):
    """
    Process each line of serial data and convert the hex values to floats.
    """
    processed_data = {}
    parts = line.split(',')

    if len(parts) >= 3 and parts[0] in units:
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
        print("\nKeyboard Interrupt detected, stopping data collection...")
        raise  # Re-raise the exception to trigger the save process
    finally:
        if ser.isOpen():
            ser.close()
            print("Serial port closed.")

def display_data(data):
    """
    Display the data, converting float values and adding units.
    """
    for key, value in data.items():
        if key != 'timestamp':
            unit = units.get(key.split('_')[0], '')
            print(f"{key}: {value:.2f} {unit}")
    
    print(f"Timestamp: {data['timestamp']}")
    print("-" * 40)

def save_data_to_csv(data_list, filename):
    """
    Save the collected data to a CSV file.
    """
    if not data_list:
        return
    
    keys = list(data_list[0].keys())
    with open(filename, 'w', newline='') as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(data_list)
    print(f"Data successfully saved to {filename}.")

def get_save_location():
    """
    Get the location where to save the CSV file.
    """
    save_location = input("Enter the path to save the CSV file (including file name): ")
    if not save_location:
        save_location = 'serial_data.csv'
    return save_location

if __name__ == '__main__':
    data_list = []

    port = find_serial_port()
    if port:
        serial_port = configure_serial(port)
        if serial_port:
            try:
                read_and_process_data(data_list, serial_port)
            except KeyboardInterrupt:
                # Ask for save location or save by default
                save_location = get_save_location()
                save_data_to_csv(data_list, save_location)
                print("Process terminated and data saved.")
        else:
            print("Failed to configure serial port.")
    else:
        print("No serial port found.")

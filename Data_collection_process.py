import serial
import serial.tools.list_ports
import struct
import time
from datetime import datetime

from random_gen import *
from Table_Graph import *

# Constants and configuration
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
    'Battery Ah': 'Ah'
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

def read_and_process_data(data_list, tab_axes, combined_ax, tables, root):
    try:
        interval_data = {}
        def update_data():
            nonlocal interval_data
            hex_lines = generate_random_data()
            for line in hex_lines:
                line = line.strip()
                processed_data = process_serial_data(line)
                if processed_data:
                    interval_data.update(processed_data)
            
            # Simulate a timestamp in TL_TIM format
            timestamp = datetime.now().strftime('%H:%M:%S')
            interval_data['timestamp'] = timestamp
            data_list.append(interval_data.copy())

            # Update plot data queues
            for key in units.keys():
                plot_data[key].append(interval_data.get(f"{key}_Value1", 0))
            timestamps.append(timestamp)

            # Update plots and tables
            update_plots_and_tables(tab_axes, combined_ax, tables, timestamps, plot_data)

            interval_data.clear()
            root.after(1000, update_data)  # Schedule the next update

        update_data()  # Start the first update
    except KeyboardInterrupt:
        print("Stopping data generation due to KeyboardInterrupt.")
        raise  # Re-raise the KeyboardInterrupt to handle it in the main loop
# data_processing.py
import struct
import serial
import serial.tools.list_ports
import time
from collections import deque

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

plot_window_size = 15
plot_data = {key: deque(maxlen=plot_window_size) for key in units.keys()}
timestamps = deque(maxlen=plot_window_size)

def hex_to_float(hex_data):
    try:
        if hex_data.startswith("0x"):
            hex_data = hex_data[2:]

        if "HHHHHHHH" in hex_data:
            return 0.0
        
        if len(hex_data) != 8:
            raise ValueError(f"Invalid hex length: {hex_data}")
        
        byte_data = bytes.fromhex(hex_data)
        float_value = struct.unpack('<f', byte_data)[0]
        
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

def list_serial_ports():
    """List all available serial ports on the system."""
    ports = serial.tools.list_ports.comports()
    return [port.device for port in ports]

def configure_serial(port, baudrate=9600, timeout=1):
    try:
        ser = serial.Serial(port, baudrate, timeout=timeout)
        print(f"Connected to {port} at {baudrate} baud.")
        return ser
    except serial.SerialException as e:
        print(f"Error opening serial port {port}: {e}")
        return None

def read_from_serial(ser):
    if ser is not None and ser.is_open:
        try:
            line = ser.readline().decode('utf-8').strip()
            return line
        except serial.SerialException as e:
            print(f"Error reading from serial port: {e}")
            return None
    return None

def search_and_connect(baudrate=9600, timeout=1):
    """Continually search for an available serial port and connect."""
    while True:
        ports = list_serial_ports()
        if ports:
            for port in ports:
                ser = configure_serial(port, baudrate, timeout)
                if ser:
                    return ser
        print("No available serial ports found. Retrying in 5 seconds...")
        time.sleep(5)
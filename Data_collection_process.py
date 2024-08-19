# Data_collection_process.py
from collections import deque
from datetime import datetime
import serial
import struct
import serial.tools.list_ports

# Unit definitions
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

# Plot window size
plot_window_size = 15
plot_data = {key: deque(maxlen=plot_window_size) for key in units.keys()}
timestamps = deque(maxlen=plot_window_size)

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
        float_value = struct.unpack('<f', byte_data)[0]  # Little-endian order
        
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

def read_and_process_data(data_list, ser, update_callback):
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
                        current_time = datetime.now().strftime('%H:%M:%S')
                        interval_data['timestamp'] = timestamp
                        interval_data['24hr_time'] = current_time  # Add 24-hour time
                        data_list.append(interval_data.copy())
                        update_callback(interval_data)
                        interval_data.clear()
    except serial.SerialException as e:
        print(f"Serial exception: {e}")
    except KeyboardInterrupt:
        print("Stopping serial read due to KeyboardInterrupt.")
        raise 
    finally:
        if ser.isOpen():
            ser.close()
            print("Serial port closed.")

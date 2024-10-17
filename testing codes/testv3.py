import struct
import serial
import serial.tools.list_ports
import threading
import time
import csv
from datetime import datetime

# Updated units and key descriptions
units = {
    'MC1BUS_Voltage': 'V',
    'MC1BUS_Current': 'A',
    'MC1VEL_Velocity': 'm/s',
    'MC1VEL_RPM': 'RPM',
    'MC2BUS_Voltage': 'V',
    'MC2BUS_Current': 'A',
    'MC2VEL_Velocity': 'm/s',
    'MC2VEL_RPM': 'RPM',
    'BP_VMX_ID': '#',
    'BP_VMX_Voltage': 'V',
    'BP_VMN_ID': '#',
    'BP_VMN_Voltage': 'V',
    'BP_TMX_ID': '#',
    'BP_TMX_Temperature': '°C',
    'BP_ISH_SOC': '%',
    'BP_ISH_milliamp': 'mA',
    'BP_PVS_Voltage': 'V',
    'BP_PVS_milliamp/s': 'mA/s'
}

# Error and limit flag descriptions
error_flags_desc = [
    "Hardware over current",
    "Software over current",
    "DC Bus over voltage",
    "Bad motor position hall sequence",
    "Watchdog caused last reset",
    "Config read error",
    "15V Rail UVLO",
    "Desaturation Fault",
    "Motor Over Speed"
]

limit_flags_desc = [
    "Output Voltage PWM",
    "Motor Current",
    "Velocity",
    "Bus Current",
    "Bus Voltage Upper Limit",
    "Bus Voltage Lower Limit",
    "IPM/Motor Temperature"
]

data_lock = threading.Lock()  # Lock to handle shared data access
stop_threads = False  # Flag to stop the threads gracefully

def find_virtual_serial_port():
    ports = serial.tools.list_ports.comports()
    virtual_ports = []
    for port in ports:
        if "virtual" in port.description.lower() or "com0com" in port.description.lower():
            virtual_ports.append(port.device)

    if virtual_ports:
        print(f"Available virtual ports: {virtual_ports}")
        return virtual_ports[1]
    else:
        print("No virtual ports found.")
        return None
    
def find_serial_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        return port.device
    return None

def configure_serial(port, baudrate=9600, timeout=1, buffer_size=2097152):
    try:
        ser = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
        
        # Set the input (RX) and output (TX) buffer sizes to 2MB
        ser.set_buffer_size(rx_size=buffer_size, tx_size=buffer_size)
        
        if ser.isOpen():
            print(f"Serial port {port} opened successfully with 2MB buffer.")
        return ser
    except serial.SerialException as e:
        print(f"Error opening serial port {port}: {e}")

def hex_to_float(hex_data):
    try:
        if hex_data == 'HHHHHHHH':
            return 0.0
        if hex_data.startswith("0x"):
            hex_data = hex_data[2:]
        if len(hex_data) != 8:
            return 0.0
        byte_data = bytes.fromhex(hex_data)
        return struct.unpack('<f', byte_data)[0]  # Little-endian float
    except (ValueError, struct.error):
        return 0.0

def hex_to_bits(hex_data):
    return f"{int(hex_data, 16):064b}"

def parse_error_and_limit_flags(error_bits, limit_bits):
    errors = []
    limits = []
    for i in range(9):
        if error_bits[15 - i] == '1':
            errors.append(error_flags_desc[i])
    for i in range(7):
        if limit_bits[15 - i] == '1':
            limits.append(limit_flags_desc[i])
    return errors, limits

def parse_motor_controller_data(hex1, hex2):
    bits1 = hex_to_bits(hex1)
    bits2 = hex_to_bits(hex2)
    can_receive_error_count = int(bits1[0:8], 2)
    can_transmit_error_count = int(bits1[8:16], 2)
    active_motor_info = int(bits1[16:32], 2)
    error_bits = bits2[32:48]
    limit_bits = bits2[48:64]
    errors, limits = parse_error_and_limit_flags(error_bits, limit_bits)
    return {
        "CAN Receive Error Count": can_receive_error_count,
        "CAN Transmit Error Count": can_transmit_error_count,
        "Active Motor Info": active_motor_info,
        "Errors": errors,
        "Limits": limits
    }

def process_serial_data(line):
    processed_data = {}
    parts = line.split(',')
    if len(parts) >= 3:
        key = parts[0]
        hex1 = parts[1].strip()
        hex2 = parts[2].strip()
        if key.startswith('MC1LIM') or key.startswith('MC2LIM'):
            motor_data = parse_motor_controller_data(hex1, hex2)
            processed_data[key] = motor_data 
        else:
            float1 = hex_to_float(hex1)
            float2 = hex_to_float(hex2)

            match key:
                case 'MC1BUS':
                    processed_data[f"{key}_Voltage"] = float1
                    processed_data[f"{key}_Current"] = float2
                case 'MC2BUS':
                    processed_data[f"{key}_Voltage"] = float1
                    processed_data[f"{key}_Current"] = float2
                case 'MC1VEL':
                    processed_data[f"{key}_Velocity"] = float1
                    processed_data[f"{key}_RPM"] = float2
                case 'MC2VEL':
                    processed_data[f"{key}_Velocity"] = float1
                    processed_data[f"{key}_RPM"] = float2
                case 'BP_VMX':
                    processed_data[f"{key}_ID"] = float1
                    processed_data[f"{key}_Voltage"] = float2
                case 'BP_VMN':
                    processed_data[f"{key}_ID"] = float1
                    processed_data[f"{key}_Voltage"] = float2
                case 'BP_TMX':
                    processed_data[f"{key}_ID"] = float1
                    processed_data[f"{key}_Temperature"] = float2
                case 'BP_ISH':
                    processed_data[f"{key}_SOC"] = float1
                    processed_data[f"{key}_milliamp"] = float2
                case 'BP_PVS':
                    processed_data[f"{key}_Voltage"] = float1
                    processed_data[f"{key}_milliamp/s"] = float2

    return processed_data

def read_serial_data(ser, data_list):
    try:
        buffer = ""
        interval_data = {}
        while not stop_threads:
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
                        interval_data['device_timestamp'] = timestamp
                        interval_data['system_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        with data_lock:
                            data_list.append(interval_data.copy())
                        interval_data.clear()
                    ser.reset_input_buffer()
            else:
                time.sleep(1)  # Reduced sleep to make it more responsive
    except serial.SerialException as e:
        print(f"Serial exception: {e}")
    except KeyboardInterrupt:
        raise
    finally:
        if ser.isOpen():
            ser.close()

def display_data(data_list):
    while not stop_threads:
        with data_lock:
            if data_list:
                latest_data = data_list[-1]
                for key, value in latest_data.items():
                    if isinstance(value, dict):
                        print(f"\n{key} Motor Controller Data:")
                        print(f"  CAN Receive Error Count: {value['CAN Receive Error Count']}")
                        print(f"  CAN Transmit Error Count: {value['CAN Transmit Error Count']}")
                        print(f"  Active Motor Info: {value['Active Motor Info']}")
                        print(f"  Errors: {', '.join(value['Errors']) if value['Errors'] else 'None'}")
                        print(f"  Limits: {', '.join(value['Limits']) if value['Limits'] else 'None'}")
                    else:
                        unit = units.get(key, '')
                        if isinstance(value, (int, float)):
                            print(f"{key}: {value:.2f} {unit}")
                        else:
                            print(f"{key}: {value} {unit}")
                print(f"Device Timestamp: {latest_data.get('device_timestamp', 'No Timestamp')}")
                print(f"System Time: {latest_data.get('system_time', 'No Timestamp')}")
                print("----------------------------------------")
        time.sleep(5)  # Reduced sleep time for faster refresh

def save_data_to_csv(data_list, filename):
    if not data_list:
        return
    keys = list(data_list[0].keys())
    with open(filename, 'w', newline='') as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(data_list)
    print(f"Data successfully saved to {filename}.")

def get_save_location():
    save_location = input("Enter the path to save the CSV file (including file name): ")
    if not save_location:
        save_location = 'serial_data.csv'
    return save_location

if __name__ == '__main__':
    data_list = []
    port = find_serial_port()
    if port:
        serial_port = configure_serial(port, buffer_size=2 * 1024 * 1024)
        if serial_port:
            try:
                read_thread = threading.Thread(target=read_serial_data, args=(serial_port, data_list))
                display_thread = threading.Thread(target=display_data, args=(data_list,))
                read_thread.start()
                display_thread.start()
                read_thread.join()
                display_thread.join()
            except KeyboardInterrupt:
                save_location = get_save_location()
                save_data_to_csv(data_list, save_location)
                print("Process terminated and data saved.")
        else:
            print("Failed to configure serial port.")
    else:
        print("No serial port found.")


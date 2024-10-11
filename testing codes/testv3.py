import struct
import serial
import serial.tools.list_ports
import time
import threading
import csv
from datetime import datetime

data_list = []  # This will store the incoming data
data_lock = threading.Lock()  # A lock to prevent race conditions when accessing data_list
data_received = threading.Event()  # Event to signal when new data is available
stop_threads = False  # Flag to stop the threads gracefully

units = {
    'MC1BUS_Voltage': 'V',
    'MC1BUS_Current': 'A',
    'MC2BUS_Voltage': 'V',
    'MC2BUS_Current': 'A',
    'MC1VEL_Velocity': 'm/s',
    'MC1VEL_RPM': 'RPM',
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

error_flags_desc = [
    "Hardware over current", "Software over current", "DC Bus over voltage", "Bad motor position hall sequence",
    "Watchdog caused last reset", "Config read error", "15V Rail UVLO", "Desaturation Fault", "Motor Over Speed"
]

limit_flags_desc = [
    "Output Voltage PWM", "Motor Current", "Velocity", "Bus Current", "Bus Voltage Upper Limit", 
    "Bus Voltage Lower Limit", "IPM/Motor Temperature"
]

def find_serial_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        return port.device
    return None

def configure_serial(port, baudrate=9600, timeout=.1):
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
    errors = [error_flags_desc[i] for i in range(9) if error_bits[15 - i] == '1']
    limits = [limit_flags_desc[i] for i in range(7) if limit_bits[15 - i] == '1']
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
    """
    Process a line of serial data. Ensure that all related sensor data 
    is grouped together in one entry, and the timestamp is captured correctly.
    """
    processed_data = {}
    parts = line.split(',')
    if len(parts) >= 3:
        key = parts[0]
        if key.startswith('MC1LIM') or key.startswith('MC2LIM'):
            hex1 = parts[1].strip()
            hex2 = parts[2].strip()
            motor_data = parse_motor_controller_data(hex1, hex2)
            processed_data[key] = motor_data
        else:
            hex1 = parts[1].strip()
            hex2 = parts[2].strip()
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

        # Check if the TL_TIM timestamp exists and apply it to the processed data
        if 'TL_TIM' in line:
            timestamp = parts[1].strip()  # Assuming TL_TIM is the second item
            processed_data['device_timestamp'] = timestamp
        else:
            processed_data['device_timestamp'] = 'No Timestamp'

    return processed_data

def read_serial_data(ser):
    """
    Read from the serial port and store data in data_list.
    Ensure the new data is grouped and processed.
    """
    buffer = ""
    while not stop_threads:
        if ser.inWaiting() > 0:
            try:
                buffer += ser.read(ser.inWaiting()).decode('utf-8')
                if '\n' in buffer:
                    lines = buffer.split('\n')
                    for line in lines[:-1]:
                        line = line.strip()
                        if line and line not in ["ABCDEF", "UVWXYZ"]:
                            processed_data = process_serial_data(line)
                            if processed_data:
                                with data_lock:
                                    # Clear the old data and store new data
                                    data_list.append(processed_data)
                                    # Signal that new data is available
                                    data_received.set()

                    buffer = lines[-1]
            except serial.SerialException as e:
                print(f"Serial exception: {e}")
                break
            except Exception as e:
                print(f"Error reading serial data: {e}")
                break

def display_data():
    """
    Continuously display the latest data in a unified format.
    """
    while not stop_threads:
        # Wait for the event to be set (new data available)
        data_received.wait()
        data_received.clear()  # Clear the event flag

        with data_lock:
            if data_list:
                latest_data = data_list[-1]

                for key, value in latest_data.items():
                    # Only format numeric types with .2f
                    unit = units.get(key, '')
                    if isinstance(value, (int, float)):
                        print(f"{key}: {value:.2f} {unit}")
                    else:
                        isinstance(value, dict)
                        # Handle nested dictionaries like motor controller data
                        print(f"\n{key} Motor Controller Data:")
                        print(f"  CAN Receive Error Count: {value['CAN Receive Error Count']}")
                        print(f"  CAN Transmit Error Count: {value['CAN Transmit Error Count']}")
                        print(f"  Active Motor Info: {value['Active Motor Info']}")
                        print(f"  Errors: {', '.join(value['Errors']) if value['Errors'] else 'None'}")
                        print(f"  Limits: {', '.join(value['Limits']) if value['Limits'] else 'None'}")

                print(f"Device Timestamp: {latest_data.get('device_timestamp', 'No Timestamp')}")
                print(f"System Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("-" * 40)


def save_data_to_csv(filename):
    with data_lock:
        if data_list:
            keys = sorted(data_list[0].keys())  # Sort the keys for uniform CSV structure
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
    try:
        port = find_serial_port()
        if port:
            serial_port = configure_serial(port)
            if serial_port:
                read_thread = threading.Thread(target=read_serial_data, args=(serial_port,))
                read_thread.start()

                display_thread = threading.Thread(target=display_data)
                display_thread.start()

                # Keep the program alive and display data
                while True:
                    time.sleep(1)

    except KeyboardInterrupt:
        # Catch keyboard interrupt to save the data before exiting
        print("Keyboard Interrupt detected. Stopping threads and saving data...")

        # Set stop_threads flag to stop reading and displaying data
        stop_threads = True

        # Wait for threads to terminate
        read_thread.join()
        display_thread.join()

        # Get save location and write to CSV
        save_location = get_save_location()
        save_data_to_csv(save_location)

        print("Process terminated and data saved.")

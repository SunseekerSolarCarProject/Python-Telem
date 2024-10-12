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
    'BP_PVS_Voltage': 'V',
    'BP_PVS_milliamp/s': 'mA/s',
    'BP_ISH_milliamp': 'mA',
    'BP_ISH_SOC': '%'
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

def find_virtual_serial_port():
    """
    This function will filter out real hardware ports and return only virtual serial ports.
    """
    ports = serial.tools.list_ports.comports()
    virtual_ports = []

    for port in ports:
        # Filter for virtual ports based on common identifiers (depends on your virtual port driver)
        # Here we are filtering based on known patterns from 'com0com' and similar emulators
        if "virtual" in port.description.lower() or "com0com" in port.description.lower():
            virtual_ports.append(port.device)

    if virtual_ports:
        print(f"Available virtual ports: {virtual_ports}")
        return virtual_ports[1]  # Return the first virtual port
    else:
        print("No virtual ports found.")
        return None
    
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
            return 0.0

        # Convert hex string to bytes
        byte_data = bytes.fromhex(hex_data)

        # Unpack to float using IEEE 754 format
        float_value = struct.unpack('<f', byte_data)[0]  # Use '<f' for little-endian order

        return float_value
    except (ValueError, struct.error):
        # Return 0.0 for any errors
        return 0.0

def hex_to_bits(hex_data):
    """
    Convert a hex string to a 64-bit integer, and return the bit representation.
    """
    return f"{int(hex_data, 16):064b}"

def parse_error_and_limit_flags(error_bits, limit_bits):
    """
    Parse error flags and limit flags from the bit strings.
    """
    errors = []
    limits = []

    # Parse error flags (bits 0-8)
    for i in range(9):
        if error_bits[15 - i] == '1':  # Error flags start at bit 8 in the lower half
            errors.append(error_flags_desc[i])

    # Parse limit flags (bits 0-6)
    for i in range(7):
        if limit_bits[15 - i] == '1':  # Limit flags start at bit 0
            limits.append(limit_flags_desc[i])

    return errors, limits

def parse_motor_controller_data(hex1, hex2):
    """
    Parse the first and second hex strings for motor controller data.
    First hex: CAN receive/transmit errors and active motor.
    Second hex: Error flags and limit flags.
    """
    bits1 = hex_to_bits(hex1)  # Convert hex1 to 64 bits
    bits2 = hex_to_bits(hex2)  # Convert hex2 to 64 bits

    # First string (hex1) parsing
    can_receive_error_count = int(bits1[0:8], 2)
    can_transmit_error_count = int(bits1[8:16], 2)
    active_motor_info = int(bits1[16:32], 2)

    # Second string (hex2) parsing for error and limit flags
    error_bits = bits2[32:48]  # Error flags (bits 31-16)
    limit_bits = bits2[48:64]  # Limit flags (bits 15-0)
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
    Process each line of serial data and convert the hex values to floats.
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
            # Convert hex to float
            float1 = hex_to_float(hex1)
            float2 = hex_to_float(hex2)

        # Process each sensor based on its type and format
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
                        # Device timestamp
                        timestamp = line.split(',')[1].strip()
                        interval_data['device_timestamp'] = timestamp

                        # Local system time
                        system_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        interval_data['system_time'] = system_time

                        # Add to the data list
                        data_list.append(interval_data.copy())
                        
                        # Display data
                        display_data(interval_data)
                        
                        # Clear interval data for next reading
                        interval_data.clear()
                    ser.reset_input_buffer()

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
        if key not in ['timestamp', 'system_time']:
            if isinstance(value, dict):
                #display motor controller information
                print(f"\n{key} Motor Controller Data:")
                print(f"  CAN Receive Error Count: {value['CAN Receive Error Count']}")
                print(f"  CAN Transmit Error Count: {value['CAN Transmit Error Count']}")
                print(f"  Active Motor Info: {value['Active Motor Info']}")
                print(f"  Errors: {', '.join(value['Errors']) if value['Errors'] else 'None'}")
                print(f"  Limits: {', '.join(value['Limits']) if value['Limits'] else 'None'}")
            else:
                #sensor data with units
                unit = units.get(key, '')
                if isinstance(value, (int, float)):
                    print(f"{key}: {value:.2f} {unit}")
                else:
                    print(f"{key}: {value} {unit}")


    if 'device_timestamp' in data:
        print(f"Device Timestamp: {data['device_timestamp']}")
    if 'system_time' in data:
        print(f"System Time: {data['system_time']}")
    print("-" * 40)
 
    
def save_data_to_csv(data_list, filename):
    """
    Save the collected data to a CSV file.
    """
    if not data_list:
        return

   #Included device timestamp and system time 
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
    #port = find_virtual_serial_port()
    if port:
        serial_port = configure_serial(port)
        if serial_port:
            #read_thread = threading.Thread(target=read_and_process_data, args=(serial_port,))
            #read_thread.daemon = True
            #read_thread.start()
            
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

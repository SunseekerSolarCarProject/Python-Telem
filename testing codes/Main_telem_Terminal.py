import struct
import serial
import serial.tools.list_ports
import threading
import time
import platform
import csv
from datetime import datetime

# Updated units and key descriptions
units = {
    'DC_DRV_Motor_Velocity_setpoint': '#',
    'DC_DRV_Motor_Currrent_setpoint': '#',
    'DC_SWC_Position': ' ',
    'DC_SWC_Values1': '#',
    'MC1BUS_Voltage': 'V',
    'MC1BUS_Current': 'A',
    'MC2BUS_Voltage': 'V',
    'MC2BUS_Current': 'A',
    'MC1VEL_Velocity': 'M/s',
    'MC1VEL_Speed': 'Mph',
    'MC1VEL_RPM': 'RPM',
    'MC2VEL_Velocity': 'M/s',
    'MC2VEL_Speed': 'Mph',
    'MC2VEL_RPM': 'RPM',
    'BP_VMX_ID': '#',
    'BP_VMX_Voltage': 'V',
    'BP_VMN_ID': '#',
    'BP_VMN_Voltage': 'V',
    'BP_TMX_ID': '#',
    'BP_TMX_Temperature': '°F',
    'BP_PVS_Voltage': 'V',
    'BP_PVS_milliamp/s': 'mA/s',
    'BP_PVS_Ah': 'Ah',
    'BP_ISH_Amps': 'A',
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

# Steering wheel control description based on Hex maps
steering_wheel_desc = {
    '0x08000000': 'regen',
    '0x00040100': 'left turn',
    '0x00040000': 'left turn',
    '0x00080000': 'right turn',
    '0x00080200': 'right turn',
    '0x00010000': 'horn',
    '0x00020300': 'hazards',
    '0x00020000': 'hazards',
    '0x00000000': 'none'
}

"""
virtual ports is meant to use virtual comm ports form applications like com0com apllication
or the expensive application for virtual com ports though the com0com is a bit difficult for the software to recognize.
"""
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
    """
    Find the first available USB serial port, adapting to Windows or macOS.
    On macOS: filters out Bluetooth devices and looks for usbserial or usbmodem.
    On Windows: looks for COM ports and filters out Bluetooth devices.
    most on mac needs to look for the tty.serial part as that is what our modems 
    recognize on mac.
    """
    ports = serial.tools.list_ports.comports()
    system_os = platform.system()

    if system_os == "Darwin":  # macOS
        for port in ports:
            # macOS: Filter out Bluetooth and look for usbserial or usbmodem in the device name
            if 'Bluetooth' not in port.description and ('tty.serial' in port.device): # or 'usbserial' in port.device or 'usbmodem' in port.device):
                try:
                    # Try to open the serial port to ensure it's available
                    ser = serial.Serial(port.device)
                    ser.close()  # Close it after confirming it's available
                    print(f"Found available USB serial port on macOS: {port.device}")
                    return port.device
                except serial.SerialException:
                    print(f"Port {port.device} is in use or unavailable.")
        print("No available USB serial ports found on macOS.")

    elif system_os == "Windows":  # Windows
        for port in ports:
            # Windows: Filter for COM ports and exclude Bluetooth devices
            if 'Bluetooth' not in port.description and port.device.startswith('COM'):
                try:
                    # Try to open the serial port to ensure it's available
                    ser = serial.Serial(port.device)
                    ser.close()  # Close it after confirming it's available
                    print(f"Found available USB serial port on Windows: {port.device}")
                    return port.device
                except serial.SerialException:
                    print(f"Port {port.device} is in use or unavailable.")
        print("No available USB serial ports found on Windows.")

    else:
        print(f"Unsupported operating system: {system_os}")
        return None

'''
if any of the changes to how serial communication happens this is where to change the values.
'''
def configure_serial(port, baudrate=9600, timeout=1, buffer_size=4194304):
    try:
        ser = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
        
        # Set the input (RX) and output (TX) buffer sizes to 4MB
        ser.set_buffer_size(rx_size=buffer_size, tx_size=buffer_size)
        
        if ser.isOpen():
            print(f"Serial port {port} opened successfully with 4MB buffer.")
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
    Convert a hex string to a 32-bit integer, and return the bit representation.
    """
    return f"{int(hex_data, 16):032b}"

def calculate_battery_capacity(capacity_ah, voltage, quantity, series_strings):
    try:
        parallel_strings = quantity // series_strings
        total_capacity_ah = capacity_ah * parallel_strings
        total_voltage = voltage * series_strings
        total_capacity_wh = total_capacity_ah * total_voltage

        return {
            'total_capacity_wh': total_capacity_wh,
            'total_capacity_ah': total_capacity_ah,
            'total_voltage': total_voltage,
        }
    except Exception as e:
        return {'error': str(e)}

def calculate_remaining_capacity(used_Ah, battery_capacity_Ah, shunt_current, time_interval):
    used_capacity = (shunt_current * time_interval) / 3600  # Convert to Ah
    remaining_Ah = battery_capacity_Ah - used_capacity - used_Ah
    return remaining_Ah

def calculate_remaining_time(remaining_Ah, shunt_current):
    if shunt_current == 0:
        return float('inf')  # Infinite time if no current draw
    remaining_time = remaining_Ah / shunt_current  # Time in hours
    return remaining_time

def calculate_watt_hours(remaining_Ah, battery_voltage):
    return remaining_Ah * battery_voltage

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

def parse_swc_data(hex1, hex2):
    """
    Parse the SWC data from two sources:
    - hex1: The first 32-bit hexadecimal string (for SWC bits 0-4).
    - swc_value: The second 32-bit raw SWC value.
    """
    bits2 = hex_to_bits(hex2)
    swc_description = steering_wheel_desc.get(hex1, "unknown") # Parse the SWC bits

    return {
        "SWC_States": swc_description,
        "SWC_Value": bits2  # Assuming this is directly a 32-bit integer
    }

def parse_motor_controller_data(hex1, hex2):
    """
    Parse the first and second hex strings for motor controller data.
    First hex: CAN receive/transmit errors and active motor.
    Second hex: Error flags and limit flags.
    """
    bits1 = hex_to_bits(hex1)  # Convert hex1 to 32 bits
    bits2 = hex_to_bits(hex2)  # Convert hex2 to 32 bits

    # First string (hex1) parsing
    can_receive_error_count = int(bits1[0:8], 2)
    can_transmit_error_count = int(bits1[8:16], 2)
    active_motor_info = int(bits1[16:32], 2)

    # Second string (hex2) parsing for error and limit flags
    error_bits = bits2[0:16]  # Error flags (bits 31-16)
    limit_bits = bits2[16:32]  # Limit flags (bits 15-0)
    errors, limits = parse_error_and_limit_flags(error_bits, limit_bits)

    return {
        "CAN Receive Error Count": can_receive_error_count,
        "CAN Transmit Error Count": can_transmit_error_count,
        "Active Motor Info": active_motor_info,
        "Errors": errors,
        "Limits": limits
    }

def convert_mps_to_mph(mps):
    return mps * 2.23964

def convert_mA_s_to_Ah(mA_s):
    return (mA_s / 1000) / 3600


def process_serial_data(line):
    """
    Process each line of serial data and convert the hex values to floats or bits.
    This is based on the First part of the serial which is the names to each value
    that is being determined.
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
        elif key.startswith('DC_SWC'):
            # Parse SWC data
            hex1 = parts[1].strip()
            hex2 = parts[2].strip()
            swc_data = parse_swc_data(hex1,hex2)
            processed_data[key] = swc_data
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
                processed_data[f"{key}_RPM"] = float1
                processed_data[f"{key}_Velocity"] = float2
                processed_data[f"{key}_Speed"] = convert_mps_to_mph(float2)
            case 'MC2VEL':
                processed_data[f"{key}_Velocity"] = float1
                processed_data[f"{key}_RPM"] = float2
                processed_data[f"{key}_Speed"] = convert_mps_to_mph(float2)
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
                processed_data[f"{key}_Amps"] = float2
            case 'BP_PVS':
                processed_data[f"{key}_Voltage"] = float1
                processed_data[f"{key}_milliamp/s"] = float2
                processed_data[f"{key}_Ah"] = convert_mA_s_to_Ah(float2)
            case 'DC_DRV':
                processed_data[f"{key}_Motor_Velocity_setpoint"] = float1
                processed_data[f"{key}_Motor_Current_setpoint"] = float2
    return processed_data

def read_and_process_data(data_list, ser, battery_info, used_Ah):
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
                    interval_data.update(battery_info)

                    if 'total_capacity_ah' in battery_info and 'total_voltage' in battery_info:
                        shunt_current = interval_data.get('BP_ISH_Amps', 0)  # Example field
                        remaining_Ah = calculate_remaining_capacity(used_Ah, battery_info['total_capacity_ah'], shunt_current, 1)
                        remaining_time = calculate_remaining_time(remaining_Ah, shunt_current)
                        remaining_wh = calculate_watt_hours(remaining_Ah, battery_info['total_voltage'])

                        # Add calculated values to interval_data
                        interval_data['remaining_Ah'] = remaining_Ah
                        interval_data['remaining_time'] = remaining_time
                        interval_data['remaining_wh'] = remaining_wh

                    buffer = lines[-1]

                    if 'TL_TIM' in line:
                        # Device timestamp
                        timestamp = line.split(',')[1].strip()
                        interval_data['device_timestamp'] = timestamp

                        # Local system time
                        system_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        interval_data['system_time'] = system_time

                        # Assume 'BP_ISH_Amps' represents the shunt current for battery usage
                        shunt_current = interval_data.get('BP_ISH_Amps', 0)

                        # Update the total used Ah
                        used_Ah += (shunt_current * 1) / 3600  # Update Ah based on the current reading

                        # Add to the data list
                        data_list.append(interval_data.copy())
                        
                        # Calculate remaining capacity and update display
                        display_data(interval_data, battery_info, used_Ah, shunt_current)
                        
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

def display_data(data, battery_info, used_Ah, shunt_current):
    """
    Display the data, converting float values and adding units.
    """
    for key, value in data.items():
        if key not in ['timestamp', 'system_time']:
            if key == 'DC_SWC':
                #display SWC state based on hex mapping
                swc_description = value.get("SWC_States", "Unkown")
                print(f"{key}: {swc_description}")
            elif isinstance(value, dict):
                #display motor controller information
                print(f"\n{key} Motor Controller Data:")
                print(f"  CAN Receive Error Count: {value.get('CAN Receive Error Count')}")
                print(f"  CAN Transmit Error Count: {value.get('CAN Transmit Error Count')}")
                print(f"  Active Motor Info: {value.get('Active Motor Info')}")
                print(f"  Errors: {', '.join(value.get('Errors', [])) if value.get('Errors') else 'None'}")
                print(f"  Limits: {', '.join(value.get('Limits', [])) if value.get('Limits') else 'None'}")
            else:
                #sensor data with units
                unit = units.get(key, '')
                if isinstance(value, (int, float)):
                    print(f"{key}: {value:.2f} {unit}")
                else:
                    print(f"{key}: {value} {unit}")

    # Display battery status
    if 'total_capacity_ah' in battery_info and 'total_voltage' in battery_info:
        remaining_Ah = calculate_remaining_capacity(used_Ah, battery_info['total_capacity_ah'], shunt_current, 1)
        remaining_time = calculate_remaining_time(remaining_Ah, shunt_current)
        remaining_wh = calculate_watt_hours(remaining_Ah, battery_info['total_voltage'])
        
        print(f"Remaining Capacity (Ah): {remaining_Ah:.2f}")
        print(f"Remaining Capacity (Wh): {remaining_wh:.2f}")
        print(f"Remaining Time (hours): {remaining_time:.2f}")

    if 'device_timestamp' in data:
        print(f"Device Timestamp: {data['device_timestamp']}")
    if 'system_time' in data:
        print(f"System Time: {data['system_time']}")
    print("-" * 40)
 
def get_user_battery_input():
    print("Please enter the following battery information:")
    capacity_ah = float(input("Battery Capacity (Ah) per cell: "))
    voltage = float(input("Battery Voltage (V) per cell: "))
    quantity = int(input("Number of cells: "))
    series_strings = int(input("Number of series strings: "))

    battery_info = calculate_battery_capacity(capacity_ah, voltage, quantity, series_strings)
    
    if 'error' in battery_info:
        print(f"Error calculating battery info: {battery_info['error']}")
        return None
    
    #display_battery_info(battery_info)
    return battery_info

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

#uncomment the vitual serial port and comment out serial port if wanting to find virtual serial 
if __name__ == '__main__':
    data_list = []

    battery_info = get_user_battery_input()
    used_Ah = 0
    if battery_info:
        port = find_serial_port()
        #port = find_virtual_serial_port()
        if port:
            serial_port = configure_serial(port, buffer_size=4 * 1024 * 1024)
            if serial_port:
                #read_thread = threading.Thread(target=read_and_process_data, args=(serial_port,))
                #read_thread.daemon = True
                #read_thread.start()
            
                try:
                    read_and_process_data(data_list, serial_port, battery_info, used_Ah)
                except KeyboardInterrupt:
                    # Ask for save location or save by default
                    save_location = get_save_location()
                    save_data_to_csv(data_list, save_location)
                    print("Process terminated and data saved.")
            else:
                print("Failed to configure serial port.")
        else:
            print("No serial port found.")

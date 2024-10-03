import struct
import serial
import serial.tools.list_ports
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
    'BP_PVS_Ah': 'mA/s',
    'BP_ISH_milliamp': 'mA',
    'BP_ISH_SOC': '%'
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
            return 0.0

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

    if len(parts) >= 3:
        key = parts[0]
        hex1 = parts[1].strip()
        hex2 = parts[2].strip()
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
            unit = units.get(key, '')
            print(f"{key}: {value:.2f} {unit}")
    
    print(f"Timestamp: {data['timestamp']}")
    print(f"System Time: {data['system_time']}")
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

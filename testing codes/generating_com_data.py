import serial
import time
import random
import serial.tools.list_ports
import struct

# Endianness configuration: 'big' or 'little'
ENDIANNESS = 'big'  # Default endianness

# Descriptions for steering wheel positions
steering_wheel_desc = {
    '0x08000000': 'regen',
    '0x00040100': 'left turn',
    '0x00040000': 'left turn',
    '0x00080000': 'right turn',
    '0x00080200': 'right turn',
    '0x00010000': 'horn',
    '0x00020300': 'hazards',
    '0x00020000': 'hazards',
    '0x00000000': 'none',
    '0xHHHHHHHH': 'nonexistent'
}

# Flag descriptions mapped to bit positions
error_flags_bits = {
    "Hardware over current": 0,
    "Software over current": 1,
    "DC Bus over voltage": 2,
    "Bad motor position hall sequence": 3,
    "Watchdog caused last reset": 4,
    "Config read error": 5,
    "15V Rail UVLO": 6,
    "Desaturation Fault": 7,
    "Motor Over Speed": 8
}

limit_flags_bits = {
    "Output Voltage PWM": 0,
    "Motor Current": 1,
    "Velocity": 2,
    "Bus Current": 3,
    "Bus Voltage Upper Limit": 4,
    "Bus Voltage Lower Limit": 5,
    "IPM/Motor Temperature": 6
}

# Constants for simulation
MAX_VALUE = 150  # Upper limit for random data generation
cycle_index = {'steering': 0, 'error': 0, 'limit': 0}  # Indices for cycling

def set_endianness():
    """Prompt user to set the desired endianness."""
    global ENDIANNESS
    while True:
        choice = input("Select endianness ('big' or 'little'): ").strip().lower()
        if choice in ['big', 'little']:
            ENDIANNESS = choice
            print(f"Endianness set to {ENDIANNESS}.")
            break
        else:
            print("Invalid choice. Please enter 'big' or 'little'.")

def float_to_hex(value):
    """
    Convert a float to an 8-character hexadecimal string representing IEEE 754 float in little endian.
    - value: The float value to convert.
    """
    # Pack the float into 4 bytes using little endian
    packed = struct.pack('<f', value)
    
    # If big endian is selected, reverse the byte order
    if ENDIANNESS == 'big':
        packed = packed[::-1]
    
    # Convert bytes to hexadecimal string
    hex_str = '0x' + packed.hex().upper()
    return hex_str

def int_to_hex(value):
    """
    Convert an integer to an 8-character hexadecimal string.
    - value: The integer value to convert.
    """
    # Mask to ensure only 32 bits
    value = value & 0xFFFFFFFF
    # Convert to bytes with specified endianness
    byte_order = 'big' if ENDIANNESS == 'big' else 'little'
    byte_value = value.to_bytes(4, byteorder=byte_order)
    # Convert bytes to hex string
    hex_str = '0x' + byte_value.hex().upper()
    return hex_str

def generate_active_motor_info():
    """Generate random motor controller info."""
    return random.randint(0, MAX_VALUE)

def next_steering_wheel_desc():
    """Cycle through steering wheel descriptions."""
    global cycle_index
    keys = list(steering_wheel_desc.keys())
    key = keys[cycle_index['steering'] % len(keys)]
    cycle_index['steering'] += 1
    return key

def cycle_flags(flag_bits, cycle_index_key):
    """
    Cycle through flags and return their combined binary value as an integer.
    Only sets one bit at a time for cycling.
    """
    global cycle_index
    flags = list(flag_bits.keys())
    bit_position = flag_bits[flags[cycle_index[cycle_index_key] % len(flags)]]
    cycle_index[cycle_index_key] += 1  # Increment the cycle index
    return 1 << bit_position  # Return the binary value with the bit set

def generate_motor_controller_data():
    """
    Simulate motor controller data.
    Uses cycling for error and limit flags.
    Returns two hex strings representing:
    - Hex1: Combined CAN receive/transmit counts and active motor info (integer)
    - Hex2: Combined error and limit flags (integer)
    """
    can_receive_error_count = random.randint(0, 5)  # Example range for CAN errors
    can_transmit_error_count = random.randint(0, 5)
    active_motor_info = random.randint(0, 100)  # Random motor information ID

    # Generate error flags as a 16-bit integer
    error_bits = cycle_flags(error_flags_bits, 'error')

    # Generate limit flags as a 16-bit integer
    limit_bits = cycle_flags(limit_flags_bits, 'limit')

    # Combine error and limit flags into a single 32-bit value
    combined_flags = (error_bits << 16) | limit_bits

    # Combine CAN counts and motor info into a single 32-bit value
    combined_counts_info = (can_receive_error_count << 24) | (can_transmit_error_count << 16) | active_motor_info

    # Convert data to hex values
    hex1 = int_to_hex(combined_counts_info)  # Integer encoding
    hex2 = int_to_hex(combined_flags)        # Integer encoding

    return hex1, hex2

def get_runtime(start_time):
    """Get elapsed runtime in HH:MM:SS format."""
    elapsed_time = int(time.time() - start_time)
    return time.strftime("%H:%M:%S", time.gmtime(elapsed_time))

def generate_data_block(runtime):
    """
    Generate a formatted data block for telemetry transmission.
    Uses IEEE 754 floating-point representations for all hex fields.
    """
    mc1lim_hex1, mc1lim_hex2 = generate_motor_controller_data()
    mc2lim_hex1, mc2lim_hex2 = generate_motor_controller_data()

    # MC1BUS: Voltage (0-160 V), Current (-20 to 90 A)
    mc1bus_voltage = random.uniform(0, 160)  # 0 to 160 V
    mc1bus_current = random.uniform(-20, 90)  # -20 to 90 A
    mc1bus_hex1 = float_to_hex(mc1bus_voltage)
    mc1bus_hex2 = float_to_hex(mc1bus_current)

    # MC1VEL: RPM (0-4000 RPM), Velocity (0-100 m/s)
    mc1vel_rpm = float(random.randint(0, 4000))  # Represented as float
    mc1vel_velocity = random.uniform(0, 100)  # 0 to 100 m/s
    mc1vel_hex1 = float_to_hex(mc1vel_rpm)
    mc1vel_hex2 = float_to_hex(mc1vel_velocity)

    # MC2BUS: Voltage (0-160 V), Current (-20 to 90 A)
    mc2bus_voltage = random.uniform(0, 160)  # 0 to 160 V
    mc2bus_current = random.uniform(-20, 90)  # -20 to 90 A
    mc2bus_hex1 = float_to_hex(mc2bus_voltage)
    mc2bus_hex2 = float_to_hex(mc2bus_current)

    # MC2VEL: RPM (0-4000 RPM), Velocity (0-100 m/s)
    mc2vel_rpm = float(random.randint(0, 4000))  # Represented as float
    mc2vel_velocity = random.uniform(0, 100)  # 0 to 100 m/s
    mc2vel_hex1 = float_to_hex(mc2vel_rpm)
    mc2vel_hex2 = float_to_hex(mc2vel_velocity)

    # DC_DRV: Setpoint (-20000 to 20000), 0-100
    dc_drv_setpoint = random.uniform(-20000, 20000)  # -20000 to 20000
    dc_drv_value = random.uniform(0, 100)  # 0 to 100
    dc_drv_hex1 = float_to_hex(dc_drv_setpoint)
    dc_drv_hex2 = float_to_hex(dc_drv_value)

    # DC_SWC
    dc_swc_position = next_steering_wheel_desc()
    dc_swc_value1 = random.getrandbits(32)
    # Convert the 32-bit integer to float
    dc_swc_float = struct.unpack('<f', dc_swc_value1.to_bytes(4, byteorder='little'))[0]
    dc_swc_value1_hex = float_to_hex(dc_swc_float)

    # BP_VMX & BP_VMN: ID (0-50), Value (0-5) with 6 decimal places
    bp_vmx_id = random.uniform(0, 50)
    bp_vmx_value = random.uniform(0, 5)
    bp_vmx_hex1 = float_to_hex(bp_vmx_id)
    bp_vmx_hex2 = float_to_hex(bp_vmx_value)

    bp_vmn_id = random.uniform(0, 50)
    bp_vmn_value = random.uniform(0, 5)
    bp_vmn_hex1 = float_to_hex(bp_vmn_id)
    bp_vmn_hex2 = float_to_hex(bp_vmn_value)

    # BP_TMX: ID (0-50), Temperature (-40 to 180) with 8 decimal places
    bp_tmx_id = random.uniform(0, 50)
    bp_tmx_temp = random.uniform(-40, 180)
    bp_tmx_hex1 = float_to_hex(bp_tmx_id)
    bp_tmx_hex2 = float_to_hex(bp_tmx_temp)

    # BP_ISH: Value (0-100), Current (-20 to 90) with 8 decimal places
    bp_ish_value = random.uniform(0, 100)
    bp_ish_current = random.uniform(-20, 90)
    bp_ish_hex1 = float_to_hex(bp_ish_value)
    bp_ish_hex2 = float_to_hex(bp_ish_current)

    # BP_PVS: 0-160, 0-146,880,000 with 8 decimal places
    bp_pvs_first = random.uniform(0, 160)
    bp_pvs_second = random.uniform(0, 146_880_000)
    bp_pvs_hex1 = float_to_hex(bp_pvs_first)
    bp_pvs_hex2 = float_to_hex(bp_pvs_second)

    # MC1LIM & MC2LIM handled by generate_motor_controller_data()

    '''MC1TP1,{mc1bus_hex1},{mc1bus_hex2}
MC1TP2,{mc1vel_hex1},{mc1vel_hex2}
MC1PHA,{mc2bus_hex1},{mc2bus_hex2}
MC1CUM,{mc2vel_hex1},{mc2vel_hex2}
MC1VVC,{mc1bus_hex1},{mc1bus_hex2}
MC1IVC,{mc1vel_hex1},{mc1vel_hex2}
MC1BEM,{mc2bus_hex1},{mc2bus_hex2}
MC2TP1,{mc2vel_hex1},{mc2vel_hex2}
MC2TP2,{mc1bus_hex1},{mc1bus_hex2}
MC2PHA,{mc1vel_hex1},{mc1vel_hex2}
MC2VVC,{mc2bus_hex1},{mc2bus_hex2}
MC2CUM,{mc2vel_hex1},{mc2vel_hex2}
MC2IVC,{mc1bus_hex1},{mc1bus_hex2}
MC2BEM,{mc1vel_hex1},{mc1vel_hex2}'''   

    return f"""ABCDEF
MC1BUS,{mc1bus_hex1},{mc1bus_hex2}
MC1VEL,{mc1vel_hex1},{mc1vel_hex2}
MC2BUS,{mc2bus_hex1},{mc2bus_hex2}
MC2VEL,{mc2vel_hex1},{mc2vel_hex2}
DC_DRV,{dc_drv_hex1},{dc_drv_hex2}
DC_SWC,{dc_swc_position},{dc_swc_value1_hex}
BP_VMX,{bp_vmx_hex1},{bp_vmx_hex2}
BP_VMN,{bp_vmn_hex1},{bp_vmn_hex2}
BP_TMX,{bp_tmx_hex1},{bp_tmx_hex2}
BP_ISH,{bp_ish_hex1},{bp_ish_hex2}
BP_PVS,{bp_pvs_hex1},{bp_pvs_hex2}
MC1LIM,{mc1lim_hex1},{mc1lim_hex2}
MC2LIM,{mc2lim_hex1},{mc2lim_hex2}
TL_TIM,{runtime}
UVWXYZ
"""

def main():
    """Main function to send data over serial port."""
    # Set endianness based on user input
    set_endianness()

    # List available COM ports
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No COM ports found.")
        return

    print("\nAvailable COM Ports:")
    for i, port in enumerate(ports):
        print(f"{i + 1}: {port.device}")

    # Allow user to select a COM port
    selected_port = None
    while selected_port is None:
        try:
            choice = int(input("Select the COM port by number: "))
            if 1 <= choice <= len(ports):
                selected_port = ports[choice - 1].device
            else:
                print("Invalid choice. Please select a valid port number.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    print("\nGenerating values starting!")
    # Set up selected COM port
    port = selected_port
    baud_rate = 19200  # Increased baud rate
    ser = None

    try:
        ser = serial.Serial(port, baud_rate, timeout=1)
        start_time = time.time()

        while True:
            loop_start_time = time.time()

            # Generate data block
            runtime = get_runtime(start_time)
            data_block = generate_data_block(runtime)

            # Send data block
            ser.write(data_block.encode('utf-8'))
            print(f"Sent data block at {runtime}")

            byte_size = len(data_block.encode('utf-8'))
            print(f"Data Block Byte Size: {byte_size} bytes")

            # Measure elapsed time
            elapsed_time = time.time() - loop_start_time
            sleep_time = 1.0 - elapsed_time
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                # Data generation and transmission took longer than 1 second
                print(f"Warning: Loop is running behind schedule by {-sleep_time:.2f} seconds")

    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except KeyboardInterrupt:
        print("\nTerminating the script.")
    finally:
        if ser and ser.is_open:
            ser.close()
            print("Serial port closed.")

if __name__ == "__main__":
    main()

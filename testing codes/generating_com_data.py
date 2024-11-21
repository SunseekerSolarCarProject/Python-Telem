import serial
import time
import random

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

def random_hex_with_limit(min_value=0, max_value=100):
    """
    Generate a random 8-digit hexadecimal value.
    Limits the range to ensure realistic values.
    """
    value = random.randint(min_value, max_value)
    return to_8bit_hex(value)

def generate_active_motor_info():
    """Generate random motor controller info."""
    return random.randint(0, MAX_VALUE)

def to_8bit_hex(value):
    """
    Ensure the given value is a valid 8-character hexadecimal string.
    - Truncate if longer than 32 bits.
    - Pad with leading zeros if shorter.
    """
    # Mask to ensure only 32 bits
    value = value & 0xFFFFFFFF
    # Format as 8-character hex string
    return f"0x{value:08X}"

def next_steering_wheel_desc():
    """Cycle through steering wheel descriptions."""
    global cycle_index
    keys = list(steering_wheel_desc.keys())
    key = keys[cycle_index['steering'] % len(keys)]
    cycle_index['steering'] += 1
    return key, steering_wheel_desc[key]

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
    """
    can_receive_error_count = random.randint(0, 5)  # Example range for CAN errors
    can_transmit_error_count = random.randint(0, 5)
    active_motor_info = random.randint(0, 100)  # Random motor information ID

    # Generate error flags as a 16-bit integer
     # Cycle through error flags (16 bits: 31–16 in the combined structure)
    error_bits = cycle_flags(error_flags_bits, 'error')

    # Cycle through limit flags (16 bits: 15–0 in the combined structure)
    limit_bits = cycle_flags(limit_flags_bits, 'limit')

    # Combine error and limit flags into a single 32-bit value
    combined_flags = (error_bits << 16) | limit_bits

    # Convert data to hex values
    hex1 = to_8bit_hex((can_receive_error_count << 24) | (can_transmit_error_count << 16) | active_motor_info)
    hex2 = to_8bit_hex(combined_flags)

    return hex1, hex2

    return hex1, hex2
def get_runtime(start_time):
    """Get elapsed runtime in HH:MM:SS format."""
    elapsed_time = int(time.time() - start_time)
    return time.strftime("%H:%M:%S", time.gmtime(elapsed_time))

def interpret_dcswc(value_hex):
    """Interpret DC_SWC value into human-readable format."""
    description = steering_wheel_desc.get(value_hex, "Unknown")
    return description

def generate_data_block(runtime):
    """
    Generate a formatted data block for telemetry transmission.
    Uses realistic ranges for data fields.
    """
    mc1lim_hex1, mc1lim_hex2 = generate_motor_controller_data()
    mc2lim_hex1, mc2lim_hex2 = generate_motor_controller_data()

    dc_swc_position, dcswc_description = next_steering_wheel_desc()
    dc_swc_value1 = random.getrandbits(32)
    dc_swc_value1_hex = to_8bit_hex(dc_swc_value1)

    return f"""ABCDEF
MC1BUS,{random_hex_with_limit(0, 600)},{random_hex_with_limit(-300, 300)}
MC1VEL,{random_hex_with_limit(0, 10000)},{random_hex_with_limit(0, 100)}
MC2BUS,{random_hex_with_limit(0, 600)},{random_hex_with_limit(-300, 300)}
MC2VEL,{random_hex_with_limit(0, 10000)},{random_hex_with_limit(0, 100)}
DC_DRV,{random_hex_with_limit(-300, 300)},{random_hex_with_limit(-300, 300)}
DC_SWC,{dc_swc_position},{dc_swc_value1_hex}
BP_VMX,{random_hex_with_limit(0, 50)},{random_hex_with_limit(0, 50)}
BP_VMN,{random_hex_with_limit(0, 50)},{random_hex_with_limit(0, 50)}
BP_TMX,{random_hex_with_limit(0, 50)},{random_hex_with_limit(-40, 100)}
BP_ISH,{random_hex_with_limit(-300, 300)},{random_hex_with_limit(-300, 300)}
BP_PVS,{random_hex_with_limit(0, 146)},{random_hex_with_limit(0, 100000000)}
MC1LIM,{mc1lim_hex1},{mc1lim_hex2}
MC2LIM,{mc2lim_hex1},{mc2lim_hex2}
TL_TIM,{runtime}
UVWXYZ
"""

def main():
    """Main function to send data over serial port."""
    import serial.tools.list_ports

    # List available COM ports
    ports = serial.tools.list_ports.comports()
    print("Available COM Ports:")
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

    print("generating values starting!")
    # Set up selected COM port
    port = selected_port
    baud_rate = 115200  # Increased baud rate
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
        print("Terminating the script.")
    finally:
        if ser:
            ser.close()

if __name__ == "__main__":
    main()


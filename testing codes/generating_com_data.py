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

# Error and limit flag descriptions
error_flags_desc = [
    "Hardware over current", "Software over current", "DC Bus over voltage",
    "Bad motor position hall sequence", "Watchdog caused last reset",
    "Config read error", "15V Rail UVLO", "Desaturation Fault", "Motor Over Speed"
]

limit_flags_desc = [
    "Output Voltage PWM", "Motor Current", "Velocity", "Bus Current",
    "Bus Voltage Upper Limit", "Bus Voltage Lower Limit", "IPM/Motor Temperature"
]

# Constants for simulation
MAX_VALUE = 150  # Upper limit for random data generation
cycle_index = {'steering': 0, 'error': 0, 'limit': 0}  # Indices for cycling

def random_hex_with_limit():
    """Generate a random 8-digit hex value within a range."""
    return f"0x{random.randint(0, MAX_VALUE):08X}"


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

def next_error_flags():
    """Cycle through error flag descriptions."""
    global cycle_index
    flag_index = cycle_index['error'] % len(error_flags_desc)
    cycle_index['error'] += 1
    return error_flags_desc[flag_index]

def next_limit_flags():
    """Cycle through limit flag descriptions."""
    global cycle_index
    flag_index = cycle_index['limit'] % len(limit_flags_desc)
    cycle_index['limit'] += 1
    return limit_flags_desc[flag_index]

def random_hex_with_limit():
    """
    Generate a random 8-digit hexadecimal value.
    Ensures the value conforms to the '0xHHHHHHHH' format.
    """
    value = random.randint(-40, MAX_VALUE)
    return to_8bit_hex(value)

def generate_motor_controller_data():
    """
    Simulate motor controller data.
    Uses cycling for error and limit flags.
    """
    can_receive_error_count = 0
    can_transmit_error_count = 0
    active_motor_info = random.randint(0, MAX_VALUE)

    error_flag = next_error_flags()
    limit_flag = next_limit_flags()

    # Simulate hex representations of error and limit bits
    error_bits = "0" * 16  # Placeholder, cycling is descriptive
    limit_bits = "0" * 16  # Placeholder, cycling is descriptive

    hex1 = to_8bit_hex((can_receive_error_count << 24) | (can_transmit_error_count << 16) | active_motor_info)
    hex2 = to_8bit_hex(int(error_bits + limit_bits, 2))

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
    Ensures all hex values are compressed to the '0xHHHHHHHH' format.
    """
    mc1lim_hex1, mc1lim_hex2 = generate_motor_controller_data()
    mc2lim_hex1, mc2lim_hex2 = generate_motor_controller_data()

    # DC_SWC example values
    dc_swc_position, dcswc_description = next_steering_wheel_desc()
    dc_swc_value1 = random.getrandbits(32)
    dc_swc_value1_hex = to_8bit_hex(dc_swc_value1)

    return f"""ABCDEF
MC1BUS,{random_hex_with_limit()},{random_hex_with_limit()}
MC1VEL,{random_hex_with_limit()},{random_hex_with_limit()}
MC2BUS,{random_hex_with_limit()},{random_hex_with_limit()}
MC2VEL,{random_hex_with_limit()},{random_hex_with_limit()}
DC_DRV,{random_hex_with_limit()},{random_hex_with_limit()}
DC_SWC,{dc_swc_position},{dc_swc_value1_hex}
BP_VMX,{random_hex_with_limit()},{random_hex_with_limit()}
BP_VMN,{random_hex_with_limit()},{random_hex_with_limit()}
BP_TMX,{random_hex_with_limit()},{random_hex_with_limit()}
BP_ISH,{random_hex_with_limit()},{random_hex_with_limit()}
BP_PVS,{random_hex_with_limit()},{random_hex_with_limit()}
MC1LIM,{mc1lim_hex1},{mc1lim_hex2}
MC2LIM,{mc2lim_hex1},{mc2lim_hex2}
TL_TIM,{runtime}
UVWXYZ
"""


def main():
    """Main function to send data over serial port."""
    # Initialize COM port (replace with your port name and baud rate)
    port = 'COM4'  # Change as needed
    baud_rate = 9600
    ser = None

    try:
        ser = serial.Serial(port, baud_rate, timeout=1)
        start_time = time.time()

        while True:
            # Generate data block
            runtime = get_runtime(start_time)
            data_block = generate_data_block(runtime)

            # Send data block
            ser.write(data_block.encode('utf-8'))

            # Wait before sending the next block
            time.sleep(5)

    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except KeyboardInterrupt:
        print("Terminating the script.")
    finally:
        if ser:
            ser.close()


if __name__ == "__main__":
    main()


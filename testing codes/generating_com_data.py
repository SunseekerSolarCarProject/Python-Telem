import serial
import time
import random

# Define error and limit flag descriptions (simulating motor controller limits)
error_flags_desc = [
    "Hardware over current", "Software over current", "DC Bus over voltage", 
    "Bad motor position hall sequence", "Watchdog caused last reset", 
    "Config read error", "15V Rail UVLO", "Desaturation Fault", "Motor Over Speed"
]

limit_flags_desc = [
    "Output Voltage PWM", "Motor Current", "Velocity", "Bus Current", 
    "Bus Voltage Upper Limit", "Bus Voltage Lower Limit", "IPM/Motor Temperature"
]

# Define maximum limit for generated data (e.g., sensor values, active motor info)
MAX_VALUE = 200

# Function to generate random 8-digit hexadecimal values within a limited range
def random_hex_with_limit():
    return f"0x{random.randint(0, MAX_VALUE):08X}"

# Function to generate a random motor info (active motor) value with limit
def generate_active_motor_info():
    return random.randint(0, MAX_VALUE)

# Function to simulate the motor controller limit data
def generate_motor_controller_data():
    can_receive_error_count = 0  # No errors
    can_transmit_error_count = 0  # No errors
    active_motor_info = generate_active_motor_info()
    
    error_bits = "0" * 16  # No errors, all bits 0
    limit_bits = bin(random.getrandbits(16))[2:].zfill(16)  # Random limits

    hex1 = f"0x{can_receive_error_count:02X}{can_transmit_error_count:02X}{active_motor_info:04X}"
    hex2 = f"0x{int(error_bits + limit_bits, 2):016X}"
    
    return hex1, hex2

# Function to get current runtime in hh:mm:ss format
def get_runtime(start_time):
    elapsed_time = int(time.time() - start_time)
    return time.strftime("%H:%M:%S", time.gmtime(elapsed_time))

# Generate formatted data block including MC1LIM and MC2LIM
def generate_data_block(runtime):
    # Generate motor controller data (MC1LIM and MC2LIM)
    mc1lim_hex1, mc1lim_hex2 = generate_motor_controller_data()
    mc2lim_hex1, mc2lim_hex2 = generate_motor_controller_data()

    return f"""ABCDEF
MC1BUS,{random_hex_with_limit()},{random_hex_with_limit()}
MC1VEL,{random_hex_with_limit()},{random_hex_with_limit()}
MC2BUS,{random_hex_with_limit()},{random_hex_with_limit()}
MC2VEL,{random_hex_with_limit()},{random_hex_with_limit()}
DC_DRV,{random_hex_with_limit()},{random_hex_with_limit()}
DC_SWC,{random_hex_with_limit()},{random_hex_with_limit()}
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

# Initialize COM port (replace with the appropriate port name)
ser = serial.Serial('COM1', 9600, timeout=1)  # Change COM5 to your virtual port

start_time = time.time()

try:
    while True:
        # Generate the data block
        runtime = get_runtime(start_time)
        data_block = generate_data_block(runtime)

        # Send the data block over the COM port
        ser.write(data_block.encode('utf-8'))

        # Wait for 1 second before sending the next block
        time.sleep(5)

except KeyboardInterrupt:
    print("Terminating the script.")

finally:
    # Close the serial port
    ser.close()

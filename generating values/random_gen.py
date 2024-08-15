import struct
import random

def generate_random_data():
    keys = ['MC1 Velocity', 'MC2 Velocity', 'MC1 Bus', 'MC2 Bus', 'BP_VMX', 'BP_VMN', 'BP_TMX', 'BP_ISH', 'BP_PVS']
    hex_lines = []
    for key in keys:
        value1 = struct.pack('<f', random.uniform(0, 100)).hex()
        value2 = struct.pack('<f', random.uniform(0, 100)).hex()
        hex_line = f"{key},0x{value1},0x{value2}"
        hex_lines.append(hex_line)
    return hex_lines

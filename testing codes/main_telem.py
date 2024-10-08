# filename: serial_data_processor_with_serial_reading.py

import struct
import serial
import serial.tools.list_ports
import time
import csv
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime
from matplotlib.animation import FuncAnimation
from tkinter import Tk, Frame, ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Define the unit labels for each data point
units = {
    'MC1 Velocity': 'm/s',
    'MC2 Velocity': 'm/s',
    'MC1 Bus': 'A',
    'MC2 Bus': 'A',
    'BP_VMX': 'V',
    'BP_VMN': 'V',
    'BP_TMX': '°C',
    'BP_ISH': 'A',
    'BP_PVS': 'V',
    'Battery mAh': 'mAh'
}

def find_serial_port():
    """
    Detect and return the first available serial port.
    
    :return: Port name if found, None otherwise
    """
    ports = serial.tools.list_ports.comports()
    for port in ports:
        return port.device
    return None

def configure_serial(port, baudrate=9600, timeout=1):
    """
    Configure the serial port with given parameters.

    :param port: Serial port name
    :param baudrate: Baud rate for the serial communication
    :param timeout: Read timeout in seconds
    :return: Configured serial object
    """
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
    Convert hex data to a single-precision float.

    :param hex_data: Hex string
    :return: Converted float value
    """
    try:
        if hex_data.startswith("0x"):
            hex_data = hex_data[2:]
        if "HHHHHHHH" in hex_data:
            return 0.0
        if len(hex_data) != 8:
            raise ValueError(f"Invalid hex length: {hex_data}")
        byte_data = bytes.fromhex(hex_data)
        float_value = struct.unpack('!f', byte_data)[0]
        return float_value
    except (ValueError, struct.error) as e:
        print(f"Error converting hex to float for data '{hex_data}': {e}")
        return None

def process_serial_data(line):
    """
    Process a single line of serial data.

    :param line: A line of serial data
    :return: Processed data as a dictionary
    """
    processed_data = {}
    parts = line.split(',')

    if parts[0] == 'TL_TIM':
        processed_data['timestamp'] = parts[1]
    else:
        key = parts[0]
        hex1 = parts[1].strip()
        hex2 = parts[2].strip()
        float1 = hex_to_float(hex1)
        float2 = hex_to_float(hex2)
        processed_data[key] = (float1, float2)
    
    return processed_data

def read_and_process_data(data_list, ser, update_interval=5000):
    """
    Read hex data from the serial port, convert it to float, and process it.

    :param data_list: List to store processed data
    :param ser: Configured serial object
    :param update_interval: Interval in milliseconds to update the plot
    """
    root = Tk()
    root.title("Real-time Data Monitor")

    notebook = ttk.Notebook(root)
    notebook.pack(fill='both', expand=True)

    figures = {}
    axes = {}
    lines = {}
    data_dict = {}

    for key in units.keys():
        frame = Frame(notebook)
        notebook.add(frame, text=key)

        fig, ax = plt.subplots()
        fig_canvas = FigureCanvasTkAgg(fig, master=frame)
        fig_canvas.get_tk_widget().pack(side='top', fill='both', expand=1)
        
        ax.set_title(key)
        ax.set_xlabel("Time")
        ax.set_ylabel(f"Value ({units[key]})")

        figures[key] = fig
        axes[key] = ax
        lines[key], = ax.plot([], [], label=key)
        data_dict[key] = []

    def animate(i):
        buffer = ""
        while ser.inWaiting() > 0:
            buffer += ser.read(ser.inWaiting()).decode('utf-8')
            if '\n' in buffer:
                lines = buffer.split('\n')
                for line in lines[:-1]:
                    line = line.strip()
                    if line and line not in ["ABCDEF", "UVWXYZ"]:
                        processed_data = process_serial_data(line)
                        if processed_data:
                            processed_data_for_purpose = process_data_for_purpose(processed_data)
                            if processed_data_for_purpose:
                                data_list.append(processed_data_for_purpose)
                buffer = lines[-1]

        timestamps = [d['timestamp'] for d in data_list]

        for key in units.keys():
            if key in data_dict:
                values = [d.get(key, 0) for d in data_list]
                data_dict[key].append(values[-1])
                axes[key].clear()
                axes[key].plot(timestamps, values, label=key)
                axes[key].set_title(key)
                axes[key].set_xlabel("Time")
                axes[key].set_ylabel(f"Value ({units[key]})")
                axes[key].legend(loc='upper left')
                axes[key].relim()
                axes[key].autoscale_view()
                plt.setp(axes[key].get_xticklabels(), rotation=45, ha='right')
                figures[key].tight_layout()

        table_frame = Frame(root)
        table_frame.pack(fill='both', expand=True)
        table = ttk.Treeview(table_frame, columns=("Value", "Unit"), show='headings')
        table.heading("Value", text="Value")
        table.heading("Unit", text="Unit")

        for key, value in data_dict.items():
            table.insert("", "end", values=(value[-1], units.get(key, "")))

        table.pack(fill='both', expand=True)

    ani = FuncAnimation(figures[list(units.keys())[0]], animate, interval=update_interval, cache_frame_data=False)
    root.mainloop()

def process_data_for_purpose(data):
    """
    Process the data for specific purposes and calculate the milliamp-hour.

    :param data: Dictionary of processed data
    :return: Dictionary of results
    """
    results = {'timestamp': data.get('timestamp')}
    
    if 'MC1VEL' in data:
        results['MC1 Velocity'] = data['MC1VEL'][0]
    if 'MC2VEL' in data:
        results['MC2 Velocity'] = data['MC2VEL'][0]
    if 'MC1BUS' in data:
        results['MC1 Bus'] = data['MC1BUS'][0]
    if 'MC2BUS' in data:
        results['MC2 Bus'] = data['MC2BUS'][0]
    if 'BP_VMX' in data:
        results['BP_VMX'] = data['BP_VMX'][0]
    if 'BP_VMN' in data:
        results['BP_VMN'] = data['BP_VMN'][0]
    if 'BP_TMX' in data:
        results['BP_TMX'] = data['BP_TMX'][0]
    if 'BP_ISH' in data:
        results['BP_ISH'] = data['BP_ISH'][0]
    if 'BP_PVS' in data:
        results['BP_PVS'] = data['BP_PVS'][0]
    
    if 'BP_ISH' in data and 'BP_PVS' in data:
        current_in_amps = data['BP_ISH'][0]
        voltage_in_volts = data['BP_PVS'][0]
        if current_in_amps is not None and voltage_in_volts is not None:
            results['Battery mAh'] = current_in_amps * voltage_in_volts * 1000
    
    return results

def save_data_to_csv(data_list, filename):
    """
    Save the processed data to a CSV file.

    :param data_list: List of processed data
    :param filename: CSV file name
    """
    if not data_list:
        return
    
    keys = data_list[0].keys()
    with open(filename, 'w', newline='') as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(data_list)

def get_save_location():
    """
    Get the CSV save location from the user.

    :return: The file path to save the CSV file
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
                save_location = get_save_location()
                save_data_to_csv(data_list, save_location)
                print(f"Data saved to {save_location}")
                print("Process terminated.")
        else:
            print("Failed to configure serial port.")
    else:
        print("No serial port found.")

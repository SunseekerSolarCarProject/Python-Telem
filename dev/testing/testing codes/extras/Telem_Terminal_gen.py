import struct
import time
import csv
from datetime import datetime
import random
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque
import tkinter as tk
from tkinter import ttk
from tkinter import font
import threading

# Constants and configuration
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

plot_window_size = 15  # Display only the last 15 data points
table_max_rows = 10  # Maximum number of rows to display in the table

# Initialize data queues for plotting
plot_data = {key: deque(maxlen=plot_window_size) for key in units.keys()}
timestamps = deque(maxlen=plot_window_size)

def hex_to_float(hex_data):
    try:
        if hex_data.startswith("0x"):
            hex_data = hex_data[2:]

        if "HHHHHHHH" in hex_data:
            return 0.0
        
        if len(hex_data) != 8:
            raise ValueError(f"Invalid hex length: {hex_data}")
        
        byte_data = bytes.fromhex(hex_data)
        float_value = struct.unpack('<f', byte_data)[0]  # Using '<f' for little-endian order
        
        if not (float('-inf') < float_value < float('inf')):
            raise ValueError(f"Unreasonable float value: {float_value}")
        
        return float_value
    except (ValueError, struct.error) as e:
        print(f"Error converting hex to float for data '{hex_data}': {e}")
        return 0.0

def process_serial_data(line):
    processed_data = {}
    parts = line.split(',')

    if parts[0] != 'TL_TIM':
        key = parts[0]
        hex1 = parts[1].strip()
        hex2 = parts[2].strip()
        float1 = hex_to_float(hex1)
        float2 = hex_to_float(hex2)
        
        processed_data[f"{key}_Value1"] = float1
        processed_data[f"{key}_Value2"] = float2
    
    return processed_data

def generate_random_data():
    """Generate random hex data for testing."""
    keys = ['MC1 Velocity', 'MC2 Velocity', 'MC1 Bus', 'MC2 Bus', 'BP_VMX', 'BP_VMN', 'BP_TMX', 'BP_ISH', 'BP_PVS']
    hex_lines = []
    for key in keys:
        # Generate two random IEEE 754 single-precision floats and convert them to hex
        value1 = struct.pack('<f', random.uniform(0, 100)).hex()  # Adjusted range to 0-100
        value2 = struct.pack('<f', random.uniform(0, 100)).hex()
        hex_line = f"{key},0x{value1},0x{value2}"
        hex_lines.append(hex_line)
    return hex_lines

def read_and_process_data(data_list, tab_axes, combined_ax, tables, root):
    try:
        interval_data = {}
        def update_data():
            nonlocal interval_data
            hex_lines = generate_random_data()
            for line in hex_lines:
                line = line.strip()
                processed_data = process_serial_data(line)
                if processed_data:
                    interval_data.update(processed_data)
            
            # Simulate a timestamp in TL_TIM format
            timestamp = datetime.now().strftime('%H:%M:%S')
            interval_data['timestamp'] = timestamp
            data_list.append(interval_data.copy())

            # Update plot data queues
            for key in units.keys():
                plot_data[key].append(interval_data.get(f"{key}_Value1", 0))
            timestamps.append(timestamp)

            # Update plots and tables
            update_plots_and_tables(tab_axes, combined_ax, tables, timestamps, plot_data)

            interval_data.clear()
            root.after(1000, update_data)  # Schedule the next update

        update_data()  # Start the first update
    except KeyboardInterrupt:
        print("Stopping data generation due to KeyboardInterrupt.")
        raise  # Re-raise the KeyboardInterrupt to handle it in the main loop

def update_plots_and_tables(tab_axes, combined_ax, tables, timestamps, plot_data):
    # Update each individual tab
    for key, ax in tab_axes.items():
        ax.clear()
        ax.plot(timestamps, plot_data[key], marker='o')
        ax.set_title(f"{key} Data")
        ax.set_xlabel("Time")
        ax.set_ylabel(units.get(key, ''))
        ax.set_xticks(timestamps)
        ax.figure.canvas.draw()

        # Update table with the latest data
        table = tables[key]

        # Ensure table only shows the last 10 values
        if len(table.get_children()) >= table_max_rows:
            table.delete(table.get_children()[0])  # Remove the oldest entry

        # Add the latest data
        table.insert('', 'end', values=(timestamps[-1], plot_data[key][-1]))

    # Update combined graph
    combined_ax.clear()
    for key, data in plot_data.items():
        combined_ax.plot(timestamps, data, marker='o', label=key)
    combined_ax.legend(loc='upper left')
    combined_ax.set_title("Combined Data")
    combined_ax.set_xlabel("Time")
    combined_ax.set_ylabel("Values")
    combined_ax.set_xticks(timestamps)
    combined_ax.figure.canvas.draw()

def save_data_to_csv(data_list, filename):
    if not data_list:
        return
    
    keys = data_list[0].keys()
    with open(filename, 'w', newline='') as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(data_list)

def get_save_location():
    save_location = input("Enter the path to save the CSV (including file name) example: C:_Users_user_downloads_csv_serial_data.csv \n")
    if not save_location:
        save_location = 'serial_data.csv'
    return save_location

def create_tabs(root, tab_control):
    tab_axes = {}
    tables = {}

    # Define a custom font for the table text
    table_font = font.Font(family="Helvetica", size=10)  # Adjust the size as needed

    # Apply the custom font to the Treeview widget
    style = ttk.Style()
    style.configure("Treeview", font=table_font)

    # Create the combined data tab
    combined_tab = ttk.Frame(tab_control)
    tab_control.add(combined_tab, text="Combined Data")
    combined_fig, combined_ax = plt.subplots(figsize=(12, 4))
    combined_canvas = FigureCanvasTkAgg(combined_fig, master=combined_tab)
    combined_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=1)

    # Create tabs for each data key
    for key in units.keys():
        tab = ttk.Frame(tab_control)
        tab_control.add(tab, text=key)

        # Create plot area
        fig, ax = plt.subplots(figsize=(10, 4))
        canvas = FigureCanvasTkAgg(fig, master=tab)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=1)
        tab_axes[key] = ax

        # Create table below the plot
        table_frame = ttk.Frame(tab)
        table_frame.pack(fill=tk.X, expand=True)
        table = ttk.Treeview(table_frame, columns=("Time", "Value"), show="headings", height=10)
        table.heading("Time", text="Time")
        table.heading("Value", text=f"Value ({units[key]})")
        table.pack(fill=tk.X, expand=True)
        tables[key] = table

    return tab_axes, combined_ax, tables

if __name__ == '__main__':
    data_list = []

    # Setup tkinter root and tabs
    root = tk.Tk()
    root.title("Real-Time Data Graphs")
    tab_control = ttk.Notebook(root)
    tab_control.pack(expand=1, fill="both")

    # Create tabs for each data key and a combined graph tab
    tab_axes, combined_ax, tables = create_tabs(root, tab_control)

    try:
        # Start reading and processing data
        root.after(0, lambda: read_and_process_data(data_list, tab_axes, combined_ax, tables, root))
        root.mainloop()
    except KeyboardInterrupt:
        print("Program interrupted. Saving data...")
        save_location = get_save_location()
        save_data_to_csv(data_list, save_location)
        print(f"Data saved to {save_location}")
        print("Process terminated.")

# main.py
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from Data_collection_process import process_serial_data, units, plot_data, timestamps
from Table_Graph import create_tabs, update_plots_and_tables
from Save_data import save_data_to_csv, get_save_location
from random_gen import generate_random_data

table_max_rows = 10

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
            
            timestamp = datetime.now().strftime('%H:%M:%S')
            interval_data['timestamp'] = timestamp
            data_list.append(interval_data.copy())

            for key in units.keys():
                plot_data[key].append(interval_data.get(f"{key}_Value1", 0))
            timestamps.append(timestamp)

            update_plots_and_tables(tab_axes, combined_ax, tables, timestamps, plot_data, units, table_max_rows)

            interval_data.clear()
            root.after(1000, update_data)

        update_data()
    except KeyboardInterrupt:
        print("Stopping data generation due to KeyboardInterrupt.")
        raise

if __name__ == '__main__':
    data_list = []

    root = tk.Tk()
    root.title("Real-Time Data Graphs")
    tab_control = ttk.Notebook(root)
    tab_control.pack(expand=1, fill="both")

    tab_axes, combined_ax, tables = create_tabs(root, tab_control, units)

    try:
        root.after(0, lambda: read_and_process_data(data_list, tab_axes, combined_ax, tables, root))
        root.mainloop()
    except KeyboardInterrupt:
        print("Program interrupted. Saving data...")
        save_location = get_save_location()
        save_data_to_csv(data_list, save_location)
        print(f"Data saved to {save_location}")
        print("Process terminated.")

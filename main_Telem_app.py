# Main.py
import tkinter as tk
from tkinter import ttk
from Data_collection_process import find_serial_port, configure_serial, read_and_process_data, plot_data, units, timestamps
from Table_Graph import create_tabs, update_plots_and_tables
from Save_data import save_data_to_csv, get_save_location
from battery_calculator import calculate_battery_capacity
import time

table_max_rows = 10 
def start_application(root, tab_control, data_list):
    port = None
    serial_port = None 
    while not port:
        port = find_serial_port()
        if port:
            serial_port = configure_serial(port)
            if serial_port:
                tab_axes, combined_ax, tables = create_tabs(root, tab_control, units)
                root.after(0, lambda: read_and_process_data(
                    data_list, serial_port, 
                    lambda data: update_plots_and_tables(tab_axes, combined_ax, tables, data, plot_data, units, table_max_rows)))
                root.mainloop()
            else:
                print("Failed to configure serial port. Retrying in 10 seconds...")
                time.sleep(10)
        else:
            print("No serial port found. Retrying in 10 seconds...")
            time.sleep(10)

def add_battery_info(data_list):
    # Prompt user for battery details
    capacity_ah = float(input("Enter the battery capacity in Ah: "))
    voltage = float(input("Enter the battery voltage: "))
    quantity = int(input("Enter the number of cells: "))
    series_strings = int(input("Enter the number of cells in series: "))

    battery_info = calculate_battery_capacity(capacity_ah, voltage, quantity, series_strings)
    data_list.append(battery_info)

if __name__ == '__main__':
    data_list = []

    root = tk.Tk()
    root.title("Real-Time Data Graphs")
    tab_control = ttk.Notebook(root)
    tab_control.pack(expand=1, fill="both")

    add_battery_info(data_list)
    start_application(root, tab_control, data_list)

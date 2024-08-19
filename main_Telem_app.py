# Main.py
import tkinter as tk
from tkinter import ttk, simpledialog
from Data_collection_process import find_serial_port, configure_serial, read_and_process_data, plot_data, units, timestamps
from Table_Graph import create_tabs, update_plots_and_tables
from Save_data import save_data_to_csv, get_save_location
from battery_calculator import calculate_battery_capacity
import time
import serial.tools.list_ports

table_max_rows = 10

def start_application(root, tab_control, data_list, serial_port):
    tab_axes, combined_ax, tables = create_tabs(root, tab_control, units)
    root.after(0, lambda: read_and_process_data(
        data_list, serial_port, 
        lambda data: update_plots_and_tables(tab_axes, combined_ax, tables, data, plot_data, units, table_max_rows)))
    root.mainloop()

def prompt_battery_info(root):
    capacity_ah = float(simpledialog.askstring("Battery Capacity", "Enter the battery capacity in Ah:", parent=root))
    voltage = float(simpledialog.askstring("Battery Voltage", "Enter the battery voltage:", parent=root))
    quantity = int(simpledialog.askstring("Number of Cells", "Enter the number of cells:", parent=root))
    series_strings = int(simpledialog.askstring("Cells in Series", "Enter the number of cells in series:", parent=root))

    return calculate_battery_capacity(capacity_ah, voltage, quantity, series_strings)

def main():
    data_list = []

    root = tk.Tk()
    root.title("Real-Time Data Graphs")
    tab_control = ttk.Notebook(root)
    tab_control.pack(expand=1, fill="both")

    # Add battery info to data list
    battery_info = prompt_battery_info(root)
    data_list.append(battery_info)

    port = find_serial_port()
    if port:
        serial_port = configure_serial(port)
        if serial_port:
            start_application(root, tab_control, data_list, serial_port)
        else:
            print("Failed to configure serial port.")
    else:
        print("No serial port found. Exiting application.")
        root.destroy()

if __name__ == '__main__':
    main()

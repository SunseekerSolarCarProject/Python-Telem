# main.py
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from Data_collection_process_gen import process_serial_data, units, plot_data, timestamps
from Table_Graph import create_tabs, update_plots_and_tables
from Save_data import save_data_to_csv, get_save_location
from random_gen import generate_random_data
from battery_calculator import calculate_battery_capacity, calculate_remaining_capacity, calculate_remaining_time, calculate_watt_hours  

table_max_rows = 10

def read_and_process_data(data_list, tab_axes, tables, root):
    interval_data = {}
    used_Ah = 0.0  # Track used capacity in Ah
    battery_capacity_Ah = 0.0
    battery_voltage = 0.0

    def update_data():
        nonlocal interval_data, used_Ah, battery_capacity_Ah, battery_voltage
        hex_lines = generate_random_data()
        for line in hex_lines:
            line = line.strip()
            processed_data = process_serial_data(line)
            if processed_data:
                interval_data.update(processed_data)

        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # Ensure that the data list and timestamp list are in sync
        data_list.append(interval_data.copy())
        timestamps.append(timestamp)

        for key in units.keys():
            plot_data[key].append(interval_data.get(f"{key}_Value1", 0))

        # Ensure timestamps and plot data are the same length
        min_length = min(len(timestamps), len(plot_data['Battery Ah']))
        timestamps = timestamps[-min_length:]
        plot_data['Battery Ah'] = plot_data['Battery Ah'][-min_length:]
        plot_data['Battery Wh'] = plot_data['Battery Wh'][-min_length:]

        # Get the current battery configuration from the user inputs
        try:
            cell_capacity_Ah = float(cell_capacity_entry.get())
            cell_voltage = float(cell_voltage_entry.get())
            num_cells = int(num_cells_entry.get())
            series_cells = int(series_cells_entry.get())

            battery_info = calculate_battery_capacity(
                capacity_ah=cell_capacity_Ah,
                voltage=cell_voltage,
                quantity=num_cells,
                series_strings=series_cells
            )

            if 'error' in battery_info:
                raise ValueError(battery_info['error'])

            battery_capacity_Ah = battery_info['total_capacity_ah']
            battery_voltage = battery_info['total_voltage']

        except ValueError:
            battery_capacity_Ah = 0.0
            battery_voltage = 0.0

        # Calculate used capacity and update it
        shunt_current = interval_data.get('BP_ISH_Value1', 0)  # Assuming this is in Amps
        used_Ah += (shunt_current / 3600)  # Update used capacity in Ah

        # Calculate remaining capacity, time, and watt-hours
        remaining_Ah = calculate_remaining_capacity(used_Ah, battery_capacity_Ah, shunt_current, 1)  # 1 second interval
        remaining_time_hours = calculate_remaining_time(remaining_Ah, shunt_current)
        remaining_wh = calculate_watt_hours(remaining_Ah, battery_voltage)

        # Update the GUI labels with calculated values
        remaining_Ah_label.config(text=f"Remaining Capacity (Ah): {remaining_Ah:.2f}")
        remaining_time_label.config(text=f"Remaining Time (h): {remaining_time_hours:.2f}")
        remaining_wh_label.config(text=f"Remaining Capacity (Wh): {remaining_wh:.2f}")

        # Update the Ah and Wh graphs
        plot_data['Battery Ah'].append(remaining_Ah)
        plot_data['Battery Wh'].append(remaining_wh)

        # Again, ensure the lengths are equal before plotting
        min_length = min(len(timestamps), len(plot_data['Battery Ah']))
        timestamps = timestamps[-min_length:]
        plot_data['Battery Ah'] = plot_data['Battery Ah'][-min_length:]
        plot_data['Battery Wh'] = plot_data['Battery Wh'][-min_length:]

        ah_ax = tab_axes.get('Battery Ah')
        wh_ax = tab_axes.get('Battery Wh')

        if ah_ax is not None:
            ah_ax.clear()
            ah_ax.plot(timestamps, plot_data['Battery Ah'], label="Remaining Ah")
            ah_ax.legend(loc="upper right")

        if wh_ax is not None:
            wh_ax.clear()
            wh_ax.plot(timestamps, plot_data['Battery Wh'], label="Remaining Wh")
            wh_ax.legend(loc="upper right")

        update_plots_and_tables(tab_axes, None, tables, timestamps, plot_data, units, table_max_rows)

        interval_data.clear()
        root.after(1000, update_data)

    update_data()
    
if __name__ == '__main__':
    data_list = []

    root = tk.Tk()
    root.title("Real-Time Data Graphs and Battery Monitoring")

    tab_control = ttk.Notebook(root)
    tab_control.pack(expand=1, fill="both")

    # Battery Parameters Input Frame
    battery_frame = ttk.Frame(root)
    battery_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

    ttk.Label(battery_frame, text="Cell Capacity (Ah):").grid(row=0, column=0, sticky=tk.W)
    cell_capacity_entry = ttk.Entry(battery_frame)
    cell_capacity_entry.grid(row=0, column=1)

    ttk.Label(battery_frame, text="Cell Voltage (V):").grid(row=1, column=0, sticky=tk.W)
    cell_voltage_entry = ttk.Entry(battery_frame)
    cell_voltage_entry.grid(row=1, column=1)

    ttk.Label(battery_frame, text="Number of Cells in Pack:").grid(row=2, column=0, sticky=tk.W)
    num_cells_entry = ttk.Entry(battery_frame)
    num_cells_entry.grid(row=2, column=1)

    ttk.Label(battery_frame, text="Series Cells:").grid(row=3, column=0, sticky=tk.W)
    series_cells_entry = ttk.Entry(battery_frame)
    series_cells_entry.grid(row=3, column=1)

    # Display Frame for Remaining Capacity, Time, and Wh
    display_frame = ttk.Frame(root)
    display_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

    remaining_Ah_label = ttk.Label(display_frame, text="Remaining Capacity (Ah): 0.00")
    remaining_Ah_label.grid(row=0, column=0, sticky=tk.W)

    remaining_time_label = ttk.Label(display_frame, text="Remaining Time (h): N/A")
    remaining_time_label.grid(row=1, column=0, sticky=tk.W)

    remaining_wh_label = ttk.Label(display_frame, text="Remaining Capacity (Wh): 0.00")
    remaining_wh_label.grid(row=2, column=0, sticky=tk.W)

    # Create Tabs and Graphs
    tab_axes, tables = create_tabs(root, tab_control, units)

    # No need for combined_ax, directly use the correct keys
    ah_ax = tab_axes.get('Battery Ah')
    wh_ax = tab_axes.get('Battery Wh')

    # Start monitoring immediately
    root.after(0, lambda: read_and_process_data(data_list, tab_axes, tables, root))

    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("Program interrupted. Saving data...")
        save_location = get_save_location()
        save_data_to_csv(data_list, save_location)
        print(f"Data saved to {save_location}")
        print("Process terminated.")

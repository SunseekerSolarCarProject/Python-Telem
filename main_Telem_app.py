import tkinter as tk
from tkinter import ttk
from datetime import datetime
from Data_collection_process import process_serial_data, search_and_connect, read_from_serial, units, plot_data, timestamps
from Table_Graph import create_tabs, update_plots_and_tables
from Save_data import save_data_to_csv, get_save_location
from battery_calculator import calculate_battery_capacity, calculate_remaining_capacity, calculate_remaining_time, calculate_watt_hours

table_max_rows = 10

def read_and_process_data(ser, data_list, tab_axes, combined_ax, tables, root):
    try:
        interval_data = {}
        used_Ah = 0  # Keep track of used capacity

        def update_data():
            nonlocal interval_data, used_Ah
            line = read_from_serial(ser)
            if line:
                processed_data = process_serial_data(line)
                if processed_data:
                    interval_data.update(processed_data)
            
            timestamp = datetime.now().strftime('%H:%M:%S')
            interval_data['timestamp'] = timestamp
            data_list.append(interval_data.copy())

            # Assume you have defined capacity, voltage, etc. (Example values used here)
            total_capacity_ah = 100  # Example: total battery capacity in Ah
            battery_voltage = interval_data.get('BP_PVS_Value1', 0)  # Voltage from the data
            shunt_current = interval_data.get('BP_ISH_Value1', 0)  # Current from the data
            time_interval = 1  # Example: 1 second interval between readings

            # Calculate remaining capacity, time, and watt-hours
            remaining_Ah = calculate_remaining_capacity(used_Ah, total_capacity_ah, shunt_current, time_interval)
            remaining_time = calculate_remaining_time(remaining_Ah, battery_voltage)
            watt_hours = calculate_watt_hours(remaining_Ah, battery_voltage)

            # Update the used_Ah with the consumed capacity
            used_Ah = total_capacity_ah - remaining_Ah

            # Include the battery-related values in the data for display
            interval_data['Remaining Ah'] = remaining_Ah
            interval_data['Remaining Time (hrs)'] = remaining_time
            interval_data['Watt Hours (Wh)'] = watt_hours

            for key in units.keys():
                plot_data[key].append(interval_data.get(f"{key}_Value1", 0))
            timestamps.append(timestamp)

            update_plots_and_tables(tab_axes, combined_ax, tables, timestamps, plot_data, units, table_max_rows)

            # Print the battery status to the console
            print(f"Remaining Ah: {remaining_Ah} Ah, Remaining Time: {remaining_time} hrs, Watt Hours: {watt_hours} Wh")

            interval_data.clear()
            root.after(1000, update_data)

        update_data()
    except KeyboardInterrupt:
        print("Stopping data reading due to KeyboardInterrupt.")
        raise

if __name__ == '__main__':
    data_list = []

    baudrate = 9600
    ser = search_and_connect(baudrate)

    root = tk.Tk()
    root.title("Real-Time Data Graphs")
    tab_control = ttk.Notebook(root)
    tab_control.pack(expand=1, fill="both")

    tab_axes, combined_ax, tables = create_tabs(root, tab_control, units)

    try:
        root.after(0, lambda: read_and_process_data(ser, data_list, tab_axes, combined_ax, tables, root))
        root.mainloop()
    except KeyboardInterrupt:
        print("Program interrupted. Saving data...")
        save_location = get_save_location()
        save_data_to_csv(data_list, save_location)
        print(f"Data saved to {save_location}")
        print("Process terminated.")
    finally:
        if ser is not None and ser.is_open:
            ser.close()

# Table_Graph.py
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import ttk, font
import tkinter as tk
from Data_collection_process import units, plot_data, timestamps

table_max_rows = 10

def create_tabs(root, tab_control, units):
    tab_axes = {}
    tables = {}

    table_font = font.Font(family="Helvetica", size=10)
    style = ttk.Style()
    style.configure("Treeview", font=table_font)

    combined_tab = ttk.Frame(tab_control)
    tab_control.add(combined_tab, text="Combined Data")
    combined_fig, combined_ax = plt.subplots(figsize=(12, 4))
    combined_canvas = FigureCanvasTkAgg(combined_fig, master=combined_tab)
    combined_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=1)

    for key in units.keys():
        tab = ttk.Frame(tab_control)
        tab_control.add(tab, text=key)

        fig, ax = plt.subplots(figsize=(10, 4))
        canvas = FigureCanvasTkAgg(fig, master=tab)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=1)
        tab_axes[key] = ax

        table_frame = ttk.Frame(tab)
        table_frame.pack(fill=tk.X, expand=True)
        
        # First Table for Value1
        table1 = ttk.Treeview(table_frame, columns=("Time", "24hr Time", "Value1"), show="headings", height=5)
        table1.heading("Time", text="Time")
        table1.heading("24hr Time", text="24hr Time")
        table1.heading("Value1", text=f"Value1 ({units[key]})")
        table1.pack(fill=tk.X, expand=True)
        
        # Second Table for Value2
        table2 = ttk.Treeview(table_frame, columns=("Time", "24hr Time", "Value2"), show="headings", height=5)
        table2.heading("Time", text="Time")
        table2.heading("24hr Time", text="24hr Time")
        table2.heading("Value2", text=f"Value2 ({units[key]})")
        table2.pack(fill=tk.X, expand=True)
        
        tables[key] = (table1, table2)

    return tab_axes, combined_ax, tables

def update_plots_and_tables(tab_axes, combined_ax, tables, interval_data, plot_data, units, table_max_rows):
    timestamp = interval_data.get('timestamp')
    current_time = interval_data.get('24hr_time')
    if timestamp and current_time:
        # Properly format the timestamps to avoid dictionary issues
        timestamps.append(f"{timestamp} ({current_time})")
        for key in units.keys():
            plot_data[key].append(interval_data.get(f"{key}_Value1", 0))

        for key, ax in tab_axes.items():
            ax.clear()
            ax.plot(list(timestamps), list(plot_data[key]), marker='o')  # Ensure the timestamps and data are lists
            ax.set_title(f"{key} Data")
            ax.set_xlabel("Time")
            ax.set_ylabel(units.get(key, ''))
            ax.set_xticks(list(timestamps))
            ax.figure.canvas.draw()

            table1, table2 = tables[key]
            if len(table1.get_children()) >= table_max_rows:
                table1.delete(table1.get_children()[0])
            if len(table2.get_children()) >= table_max_rows:
                table2.delete(table2.get_children()[0])

            table1.insert('', 'end', values=(timestamp, current_time, plot_data[key][-1]))
            table2.insert('', 'end', values=(timestamp, current_time, interval_data.get(f"{key}_Value2", 0)))

        combined_ax.clear()
        for key, data_series in plot_data.items():
            combined_ax.plot(list(timestamps), list(data_series), marker='o', label=key)  # Ensure the timestamps and data are lists
        combined_ax.legend(loc='upper left')
        combined_ax.set_title("Combined Data")
        combined_ax.set_xlabel("Time")
        combined_ax.set_ylabel("Values")
        combined_ax.set_xticks(list(timestamps))
        combined_ax.figure.canvas.draw()

# Table_Graph.py
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import ttk, font
import tkinter as tk

def create_tabs(root, tab_control, units):
    tab_axes = {}
    tables = {}

    for key in units.keys():
        tab = ttk.Frame(tab_control)
        tab_control.add(tab, text=key)

        fig, ax = plt.subplots(figsize=(10, 4))
        canvas = FigureCanvasTkAgg(fig, master=tab)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=1)
        tab_axes[key] = ax  # Use the unit key as the dictionary key

        table_frame = ttk.Frame(tab)
        table_frame.pack(fill=tk.X, expand=True)
        table = ttk.Treeview(table_frame, columns=("Time", "Value"), show="headings", height=10)
        table.heading("Time", text="Time")
        table.heading("Value", text=f"Value ({units[key]})")
        table.pack(fill=tk.X, expand=True)
        tables[key] = table  # Map table directly with key

    return tab_axes, tables

def update_plots_and_tables(tab_axes, combined_ax, tables, timestamps, plot_data, units, table_max_rows):
    # Assume starting from time = 0 and increment by 5 seconds for each new timestamp
    if len(timestamps) == 0:
        current_time = 0
    else:
        current_time = timestamps[-1] + 5
    
    timestamps.append(current_time)

    for key, ax in tab_axes.items():
        if len(timestamps) == len(plot_data[key]) and len(timestamps) > 0:
            ax.clear()
            ax.plot(timestamps, plot_data[key], marker='o')
            ax.set_title(f"{key} Data")
            ax.set_xlabel("Time (s)")
            ax.set_ylabel(units.get(key, ''))
            ax.set_xticks(timestamps)
            ax.figure.canvas.draw()

            table = tables[key]
            if len(table.get_children()) >= table_max_rows:
                table.delete(table.get_children()[0])

            # Insert the latest timestamp and data into the table
            table.insert('', 'end', values=(f"{current_time:.2f}", plot_data[key][-1]))

    if combined_ax is not None:
        combined_ax.clear()
        for key, data in plot_data.items():
            if len(timestamps) == len(data) and len(timestamps) > 0:
                combined_ax.plot(timestamps, data, marker='o', label=key)
        combined_ax.legend(loc='upper left')
        combined_ax.set_title("Combined Data")
        combined_ax.set_xlabel("Time (s)")
        combined_ax.set_ylabel("Values")
        combined_ax.set_xticks(timestamps)
        combined_ax.figure.canvas.draw()

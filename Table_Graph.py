import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from tkinter import ttk, font
from collections import deque

from Data_collection_process import units

plot_window_size = 15  # Display only the last 15 data points
table_max_rows = 10  # Maximum number of rows to display in the table

plot_data = {key: deque(maxlen=plot_window_size) for key in units.keys()}
timestamps = deque(maxlen=plot_window_size)

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
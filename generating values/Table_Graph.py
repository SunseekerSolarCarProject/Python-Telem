# table_and_graph.py
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import ttk, font
import tkinter as tk

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
        table = ttk.Treeview(table_frame, columns=("Time", "Value"), show="headings", height=10)
        table.heading("Time", text="Time")
        table.heading("Value", text=f"Value ({units[key]})")
        table.pack(fill=tk.X, expand=True)
        tables[key] = table

    return tab_axes, combined_ax, tables

def update_plots_and_tables(tab_axes, combined_ax, tables, timestamps, plot_data, units, table_max_rows):
    for key, ax in tab_axes.items():
        ax.clear()
        ax.plot(timestamps, plot_data[key], marker='o')
        ax.set_title(f"{key} Data")
        ax.set_xlabel("Time")
        ax.set_ylabel(units.get(key, ''))
        ax.set_xticks(timestamps)
        ax.figure.canvas.draw()

        table = tables[key]
        if len(table.get_children()) >= table_max_rows:
            table.delete(table.get_children()[0])

        table.insert('', 'end', values=(timestamps[-1], plot_data[key][-1]))

    combined_ax.clear()
    for key, data in plot_data.items():
        combined_ax.plot(timestamps, data, marker='o', label=key)
    combined_ax.legend(loc='upper left')
    combined_ax.set_title("Combined Data")
    combined_ax.set_xlabel("Time")
    combined_ax.set_ylabel("Values")
    combined_ax.set_xticks(timestamps)
    combined_ax.figure.canvas.draw()

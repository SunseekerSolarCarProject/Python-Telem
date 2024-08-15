import tkinter as tk
from tkinter import ttk
import random
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque
import threading
import time

# Initialize the main application window
root = tk.Tk()
root.title("Telemetry GUI")

# Initialize the notebook (tabbed interface)
notebook = ttk.Notebook(root)
notebook.pack(expand=1, fill='both')

# Tab 1: Data Stream (Random Number Generation with Graph and Data Table)
tab1 = ttk.Frame(notebook)
notebook.add(tab1, text="Data Stream")

# Graph Setup
fig, ax = plt.subplots()
canvas = FigureCanvasTkAgg(fig, master=tab1)
canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

# Data table for last 10 values
data_table = tk.Listbox(tab1, height=10)
data_table.pack(side=tk.BOTTOM, fill=tk.X)

# Data storage (last 10 values)
data_queue = deque(maxlen=10)

def update_data():
    while True:
        # Generate random data
        new_value = random.randint(0, 100)
        data_queue.append(new_value)
        
        # Update the graph
        ax.clear()
        ax.plot(list(data_queue))
        canvas.draw()
        
        # Update the data table
        data_table.delete(0, tk.END)
        for val in data_queue:
            data_table.insert(tk.END, val)
        
        time.sleep(1)

# Start the data update in a separate thread
threading.Thread(target=update_data, daemon=True).start()

# Tab 2: Battery Calculation
tab2 = ttk.Frame(notebook)
notebook.add(tab2, text="Battery Calculation")

# Input fields
tk.Label(tab2, text="Battery Capacity (Ah):").grid(row=0, column=0)
capacity_entry = tk.Entry(tab2)
capacity_entry.grid(row=0, column=1)

tk.Label(tab2, text="Battery Voltage (V):").grid(row=1, column=0)
voltage_entry = tk.Entry(tab2)
voltage_entry.grid(row=1, column=1)

tk.Label(tab2, text="Quantity of Batteries:").grid(row=2, column=0)
quantity_entry = tk.Entry(tab2)
quantity_entry.grid(row=2, column=1)

tk.Label(tab2, text="Length of Series Strings:").grid(row=3, column=0)
series_entry = tk.Entry(tab2)
series_entry.grid(row=3, column=1)

ah_label = tk.Label(tab2, text="Amp-Hours: ")
ah_label.grid(row=4, column=0, columnspan=2)
wh_label = tk.Label(tab2, text="Watt-Hours: ")
wh_label.grid(row=5, column=0, columnspan=2)

def calculate_capacity():
    try:
        capacity = float(capacity_entry.get())
        voltage = float(voltage_entry.get())
        quantity = int(quantity_entry.get())
        series = int(series_entry.get())

        total_ah = capacity * quantity / series
        total_wh = total_ah * voltage

        ah_label.config(text=f"Amp-Hours: {total_ah:.2f}")
        wh_label.config(text=f"Watt-Hours: {total_wh:.2f}")
    except ValueError:
        ah_label.config(text="Error: Invalid input")
        wh_label.config(text="")

tk.Button(tab2, text="Calculate", command=calculate_capacity).grid(row=6, column=0, columnspan=2)

# Tab 3: Shunt Current Monitoring
tab3 = ttk.Frame(notebook)
notebook.add(tab3, text="Shunt Current Monitoring")

# Shunt Current Input
tk.Label(tab3, text="Shunt Current (A):").grid(row=0, column=0)
current_entry = tk.Entry(tab3)
current_entry.grid(row=0, column=1)

ah_shunt_label = tk.Label(tab3, text="Amp-Hours from Shunt: ")
ah_shunt_label.grid(row=1, column=0, columnspan=2)
wh_shunt_label = tk.Label(tab3, text="Watt-Hours from Shunt: ")
wh_shunt_label.grid(row=2, column=0, columnspan=2)

def calculate_shunt():
    try:
        current = float(current_entry.get())
        voltage = float(voltage_entry.get())  # Reuse voltage from Tab 2

        # For simplicity, assume time delta of 1 second
        total_ah_shunt = current * 1 / 3600  # 1 second interval
        total_wh_shunt = total_ah_shunt * voltage

        ah_shunt_label.config(text=f"Amp-Hours from Shunt: {total_ah_shunt:.5f}")
        wh_shunt_label.config(text=f"Watt-Hours from Shunt: {total_wh_shunt:.5f}")
    except ValueError:
        ah_shunt_label.config(text="Error: Invalid input")
        wh_shunt_label.config(text="")

tk.Button(tab3, text="Calculate from Shunt", command=calculate_shunt).grid(row=3, column=0, columnspan=2)

# Start the Tkinter main loop
root.mainloop()

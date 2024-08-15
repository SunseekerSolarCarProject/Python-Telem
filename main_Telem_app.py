import struct
import tkinter as tk
from tkinter import ttk
import threading

from Table_Graph import create_tabs, read_and_process_data
from Data_collection_process import *
from Save_data import *

if __name__ == '__main__':
    data_list = []

    # Setup tkinter root and tabs
    root = tk.Tk()
    root.title("Real-Time Data Graphs")
    tab_control = ttk.Notebook(root)
    tab_control.pack(expand=1, fill="both")

    # Create tabs for each data key and a combined graph tab
    tab_axes, combined_ax, tables = create_tabs(root, tab_control)

    try:
        # Start reading and processing data
        root.after(0, lambda: read_and_process_data(data_list, tab_axes, combined_ax, tables, root))
        root.mainloop()
    except KeyboardInterrupt:
        print("Program interrupted. Saving data...")
        save_location = get_save_location()
        save_data_to_csv(data_list, save_location)
        print(f"Data saved to {save_location}")
        print("Process terminated.")

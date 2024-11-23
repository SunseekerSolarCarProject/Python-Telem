import pandas as pd
import re
import struct
from tkinter import Tk
from tkinter.filedialog import askopenfilename

def extract_and_convert_hex(file_path):
    # Load the data
    data = pd.read_csv(file_path)
    
    # Define a function to extract and convert hex to float (little-endian)
    def process_raw_data(raw_data):
        # Regular expression to find '0x' followed by 8 hex characters
        hex_pattern = r"(0x[0-9A-Fa-f]{8})"
        # Find all matches
        hex_matches = re.findall(hex_pattern, raw_data)
        if not hex_matches:
            return {}
        # Convert hex matches to floats (little-endian interpretation)
        converted_values = {}
        for hex_value in hex_matches:
            try:
                # Convert the hexadecimal string to bytes in little-endian order
                int_value = int(hex_value, 16)
                # Pack as little-endian and unpack as a float
                float_value = struct.unpack('!f', struct.pack('<I', int_value))[0]
                converted_values[hex_value] = float_value
            except Exception as e:
                converted_values[hex_value] = f"Error: {e}"
        return converted_values
    
    # Apply the function to the raw_data column
    data['converted_data'] = data['raw_data'].apply(lambda x: process_raw_data(str(x)))
    
    # Save the results to a new CSV file
    output_file = file_path.replace(".csv", "_processed.csv")
    data.to_csv(output_file, index=False)
    print(f"Processed data saved to: {output_file}")

def main():
    # Use tkinter file dialog to select the CSV file
    print("Please select your CSV file...")
    Tk().withdraw()  # Prevents the full Tkinter GUI from launching
    file_path = askopenfilename(title="Select a CSV file", filetypes=[("CSV files", "*.csv")])
    
    if file_path:
        print(f"Processing file: {file_path}")
        extract_and_convert_hex(file_path)
    else:
        print("No file selected. Exiting.")

if __name__ == "__main__":
    main()

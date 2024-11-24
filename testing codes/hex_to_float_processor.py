import pandas as pd
import re
import struct
from tkinter import Tk
from tkinter.filedialog import askopenfilename

def extract_and_convert_hex(file_path):
    # Load the data
    data = pd.read_csv(file_path)

    # Define which fields are floats and which are flags
    float_fields = ['MC1BUS', 'MC1VEL', 'MC2BUS', 'MC2VEL', 'DC_DRV', 'DC_SWC',
                   'BP_VMX', 'BP_VMN', 'BP_TMX', 'BP_ISH', 'BP_PVS']
    flag_fields = ['MC1LIM', 'MC2LIM']  # Add any other flag fields here

    # Define a function to extract and convert hex to float (for float fields)
    def process_float_data(raw_data, field_name):
        # Regular expression to find '0x' followed by 8 hex characters
        hex_pattern = r"(0x[0-9A-Fa-f]{8})"
        # Find all matches
        hex_matches = re.findall(hex_pattern, raw_data)
        if not hex_matches:
            return {}
        converted_values = {}
        for hex_value in hex_matches:
            try:
                # Convert the hexadecimal string to bytes in little endian order
                int_value = int(hex_value, 16)
                # Pack as little endian and unpack as a float
                float_value = struct.unpack('<f', int_value.to_bytes(4, byteorder='little'))[0]
                converted_values[hex_value] = float_value
            except Exception as e:
                converted_values[hex_value] = f"Error: {e}"
        return converted_values

    # Define a function to extract and convert hex to integer (for flag fields)
    def process_flag_data(raw_data, field_name):
        # Regular expression to find '0x' followed by 8 hex characters
        hex_pattern = r"(0x[0-9A-Fa-f]{8})"
        # Find all matches
        hex_matches = re.findall(hex_pattern, raw_data)
        if not hex_matches:
            return {}
        converted_values = {}
        for hex_value in hex_matches:
            try:
                # Convert the hexadecimal string to integer
                int_value = int(hex_value, 16)
                converted_values[hex_value] = int_value
            except Exception as e:
                converted_values[hex_value] = f"Error: {e}"
        return converted_values

    # Function to determine field type and process accordingly
    def process_field(row):
        field_data = {}
        for field in float_fields + flag_fields:
            if field in row:
                if field in float_fields:
                    field_data[field] = process_float_data(str(row[field]), field)
                elif field in flag_fields:
                    field_data[field] = process_flag_data(str(row[field]), field)
        return field_data

    # Apply the function to each row
    data['converted_data'] = data.apply(process_field, axis=1)

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

import csv

def save_data_to_csv(data_list, filename):
    if not data_list:
        return
    
    keys = data_list[0].keys()
    with open(filename, 'w', newline='') as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(data_list)

def get_save_location():
    save_location = input("Enter the path to save the CSV (including file name) example: C:_Users_user_downloads_csv_serial_data.csv \n")
    if not save_location:
        save_location = 'serial_data.csv'
    return save_location
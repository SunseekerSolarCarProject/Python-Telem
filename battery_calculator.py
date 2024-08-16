def calculate_battery_capacity(capacity_ah, voltage, quantity, series_strings):
    try:
        parallel_strings = quantity // series_strings
        total_capacity_ah = capacity_ah * parallel_strings
        total_voltage = voltage * series_strings
        total_capacity_wh = total_capacity_ah * total_voltage

        return {
            'total_capacity_wh': total_capacity_wh,
            'total_capacity_ah': total_capacity_ah,
            'total_voltage': total_voltage,
        }
    except Exception as e:
        return {'error': str(e)}
    
def calculate_remaining_capacity(used_Ah, battery_capacity_Ah, shunt_current, time_interval):
    used_capacity = (shunt_current * time_interval) / 3600  # Convert to Ah
    remaining_Ah = battery_capacity_Ah - used_capacity - used_Ah
    return remaining_Ah

def calculate_remaining_time(remaining_Ah, shunt_current):
    if shunt_current == 0:
        return float('inf')  # Infinite time if no current draw
    remaining_time = remaining_Ah / shunt_current  # Time in hours
    return remaining_time

def calculate_watt_hours(remaining_Ah, battery_voltage):
    return remaining_Ah * battery_voltage

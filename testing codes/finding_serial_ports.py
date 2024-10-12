import serial.tools.list_ports

def find_serial_port():
    ports = serial.tools.list_ports.comports()
    available_ports = [port.device for port in ports]
    print("Available ports:", available_ports)
    return available_ports
    
if __name__ == "__main__":
    find_serial_port()

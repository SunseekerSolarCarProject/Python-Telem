# main.py

from telemetry_application import TelemetryApplication

if __name__ == "__main__":
    #baudrate transmission of the rs232 is 96001
    app = TelemetryApplication(baudrate=115200)
    app.start()

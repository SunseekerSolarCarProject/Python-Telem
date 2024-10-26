# main.py

from telemetry_application import TelemetryApplication

if __name__ == "__main__":
    app = TelemetryApplication(baudrate=9600)
    app.start()

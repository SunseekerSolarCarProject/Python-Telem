<h1 align="center"> Telemetry Application </h1>
This is the newer telemetry that I have rebuilt up in python and meant for many students wanting to update the software reading it much easeir than before.
I Improved the usability of the the software a bit more and made the process of deciphering the data over serial a bit easier in the gui. The Software represents most cases of the serial data collection.
The tabs within the software reflect on what is being represented on the car.

<h2 align="left"> Location and starting the Application</h2>

### Windows
The files for the executable for windows is within the release version of github where you can download the exe file. There is also two text files that would be necessary to download. These text files have the information of the battery pack configuration. In order to get the txt to show up just put a folder name "config_files" in the same directory of the exe file. Then within the config dialog you can select those files. There are files that show up when the software starts there is two csv files and 1 log file in the beginning. The log files do expand 5 times as backup when each file reaches 20MB as the limit for the file.

### Macs
To run on Mac download the zip folder and unzip it where every you want. Then just follow the steps below.
1. The first step is download the entire project to your mac from github.
2. This is to open your terminal within that folder
3. then enter this line of code 'Python3 main_app.py' in the terminal where the the "main_app.py" is to start.
This should start the application for the code to run on your mac.

<h2 align="left"> adding new battery configurations to the software </h2>
If wanting to add new battery configs to the software dropdown follow these steps:

1. create a txt file and name the battery config file.
2. make sure the battery config files has these names in them:
    - Battery cell capacity amps hours, A value 
    - Battery cell nominal voltage, A value
    - Amount of battery cells, A value
    - Number of battery series, A value
3. save that file and put it in the configs file folder where the "main_app.exe" is located.
4. now it shows up in the drop down config for the battery to load.

### Devs
Devs that want to create a new executable for the telemetry software on windows side follow the instructions ahead. Make sure auto-py-to-exe is installed with this command 'pip install auto-py-to-exe'. then once it is installed run this command either 'auto-py-to-exe' if you are dealing in another program editor. If entering into VSCode then use this command 'python -m auto_py_to_exe' as this makes it work because the VSCode thinks that there is multiple versions of python in VSCode.

There is a entire debug feature that is implemented into this program for developers that want to see what is happening within the code if some new features break the program and can't figure out where the data is going to. The data logs are backup 5 times at each size of 20MB.
## Repository Layout (cleaned)
- `src/`: application source code
- `src/hooks/`: PyInstaller hooks (used in builds)
- `scripts/`: TUF signing/release helper scripts
- `config_files/`: battery configuration text files for runtime
- `dev/testing/`: old testing/experimental scripts moved here
- `dev/checks/`: small one-off check scripts
- `dev/packaging/`: auto-py-to-exe settings and packaging helpers
- `dist/`: build outputs (ignored by Git)
- `src/application_data/`: runtime logs/CSVs (ignored by Git)
- `combined_training_data.csv`, `wh_per_mile_summary.csv`: local dev artifacts (ignored)
- `vehicle_years.txt`: GUI dropdown values (kept at repo root)

> Note: `__pycache__/` and `*.pyc` are ignored and were cleaned from the working tree. `.venv/` remains local-only.

<h1 align="center"> Telemetry Application </h1>
This is the newer telemetry that I have rebuilt up in python and meant for many students wanting to update the software reading it much easeir than before.
I Improved the usability of the the software a bit more and made the process of deciphering the data over serial a bit easier in the gui. The Software represents most cases of the serial data collection. 
"this still has some issues currently but will be fixed in the near future for the software"

<h2 align="left"> Location and starting the Application</h2>

### Windows
The files for the executable for windows is within the release version of github where you can download the zip folder which is going to be needed to be unpacked. Then in the output folder there is an another folder that contains the name "main_app" that is where to execute the program for windows. The name being "main_app.exe".

### Macs
To run on my it is more of an execution within your mac terminal. It should look something like this to execute the file. 
1. The first step is download the entire project to your mac from github.
2. This is to open your terminal within that folder
3. then enter this line of code Python3 main_app.py
This should start the application for the code to run on your mac.

<h2 align="left"> adding new battery configurations to the software </h2>
If wanting to add new battery configs to the software dropdown follow these steps:

1. create a txt file and name the battery config file.
2. make sure the battery config files has these names in them:
    Battery capacity amps hours, A value
    Battery nominal voltage, A value
    Amount of battery cells, A value
    Number of battery strings, A value
3. save that file and put it in the configs file folder where the "main_app.exe is there.
4. now it shows up in the drop down config for the battery to load.

### Devs
Devs that created a new executable for the telemetry software on windows side goes this way. Make sure auto-py-to-exe is installed with this command 'pip install auto-py-to-exe'. then once it is installed run this command either 'auto-py-to-exe' if you are dealing in another program editor. If entering into VSCode then use this command 'python -m auto_py_to_exe' as this makes it work because the VSCode thinks that there is multiple versions of python in VSCode.

There is a entire debug feature that is implemented into this program for developers that want to see what is happening within the code if some new features break the program and can't figure out where the data is going to.
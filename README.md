<h1 align="center"> Telemetry Application </h1>
This is the newer telemetry that I have rebuilt up in python and any one can read for newcommers into coding.
I have added much functionality to the Telemetry Application to make it easily readable in the terminal and two csv's are outputed and all the data is appended to the csv's to handle if the program shutsdown and needs to restart old data is not lost.
This will be much more expansive with a gui to deal with but that is in the works currently. 

### Windows
The files for the executable for windows is within the release version of github where you can download the zip folder which is going to be needed to be unpacked. Then in the output folder there is an another folder that contains the name "main_app" that is where to execute the program is at with the name being "main_app.exe".

### Macs
To run on my it is more of an execution within your mac terminal. It should look something like this to execute the file. 
1. The first step is download the entire project to your mac from github.
2. This is to open your terminal within that folder
3. then enter this line of code Python3 main_app.py
This should start the application for the code to run on your mac.

### Devs
Devs that created a new executable for the telemetry software on windows side goes this way. Make sure auto-py-to-exe is installed with this command 'pip install auto-py-to-exe'. then once it is installed run this command either 'auto-py-to-exe' if you are dealing in another program editor. If entering into VSCode then use this command 'python -m auto_py_to_exe' as this makes it work because the VSCode thinks that there is multiple versions of python in VSCode.

There is a entire debug feature that is implemented into this program for developers that want to see what is happening within the code if some new features break the program and can't figure out where the data is going to.
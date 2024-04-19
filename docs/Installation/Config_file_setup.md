# Config files  
As all systems are different, certain aspects of the code including some paths and ports for the arduino may need to be changed between systems. Therefore we have included a couple of config files to handle this:

## Config_path.json 
_**config_path.json**_ should to be placed in the working directory</br>
_**config_path.json**_ contains the absolute or relative path to the "config folder" where all experiment-related config files are placed
</br>_Default:_ </br>
_**FreelyMovingVR4Mice**_ is considered to be the default working directory (local) </br>
The local `vr4mice/cfg` is the default "config folder" (in case of absence of _config_path.json_)


## Task config file 
This config file specifies the paths to dlc models and the unity game
Adjust absolute paths in [mouse_task/task_config.json](mouse_task/task_config.json)

"model_absolute_path": path to model to apply</br>
"dlc_video_absolute_path": path to video file to process</br>
"ar_env_unity_absolute_path": path to unity binary environment</br>

***Note: don't modify config file location and key-words in .json***


## Rig config file
This Config file specifies a few important things that control the setup of the rig: 

1. The path to the python task files. As default this should be ```mouse_task/```
2. The arduino Port, Baudrate 
3. Inputs and outputs to the arduino
4. Specifies the path where the logged data should be saved

### Creating the Rig config file
When you come to use the GUI for the first time you will have to setup the rig config file. To do this follow these steps:

- First connect the teensy to the computer using the USB cable
- Then launch the GUI 
- Open the dropdown menu under config and click on add new config, then specify: 
    - The ***serial port*** of the specific microcontroller (e.g. on windows, COM1)
    - The ***baud rate***, specified in the arduino sketch
    - List the ***inputs*** that are read from the microcontroller, separated by commas. For example, this could be lever presses.
    - For each different command you would like to write to the microcontroller, click Add Output, and provide:
    - Name for the command (e.g. water). The string character associated with the command (that you have coded into the arduino sketch; e.g. W). Parameters for the command, separated by commas (e.g. duration)
    - Add subjects as desired
    - Select a directory to save your data (select Browse from the dropdown menu to add a new directory)
    - Select your task directory 







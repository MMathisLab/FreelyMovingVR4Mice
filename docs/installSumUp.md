
The FreelyMovingVR4Mice repository contains main **vr4mice** package (src code: teensyexp folder) and **mouse_task** module that is the input for **vr4mice**
### Installation:

1. download source code

```
$ git clone TODO(add repo's lonk)
```

1. set up conda environment: (_if --name option is omitted the default name of conda environment is vr4mice_)
```
$ conda env create -f environment.yml --name name_of_env
```

2. install *vr4mice* package  (_use pip install -e . if package is under development_)
```
$ pip install .
```
3. Note: it's possible to install **vr4mice** package directly from git:

```
$ pip install TODO(add repo's lonk)
```

### Config files highlights 
_**config_path.json**_ should to be placed in the working directory</br>
_**config_path.json**_ contains the absolute or relative path to the "config folder" where all experiment-related config files are placed
</br>_Default:_ </br>
_**FreelyMovingVR4Mice**_ is considered to be the default working directory (local) </br>
The local _**vr4mice/cfg**_ is the default "config folder" (in case of absence of _config_path.json_)

### Getting Started
#### Setting up your experimental system
### Teensy part ####
  - Connect teensy microcontroller ([example of code to upload](mouse_task/teensy))
  - check rights on port access (modify via sudo chmod if needed)
### Global config file ####
  - Define a configuration file (place it in the folder defined in the _config_path.json_ file; default _/home/vr4mice/test_config_ folder)
  - TODO(tom) configuration file define serial port of the current microcontroller

### Task's config file ####
Adjust absolute paths in [mouse_task/task_config.json](mouse_task/task_config.json)

"model_absolute_path": path to model to apply</br>
"dlc_video_absolute_path": path to video file to process</br>
"ar_env_unity_absolute_path": path to unity binary environment</br>

_Note: don't modify config file location and key-words in .json_

### Start
Run: 
```
$ vr4mice
```
and gui that controls the experiment logic appears!
</br>_**Note:**_ close the program via gui via stop-close, and not via crtl-C/crtl-Z 
### Interactions with gui

First:
  - Select your desired configuration
  - Select the appropriate teensy
  - Click `connect` to establish a serial connection with the microcontroller.

Next:
  - Select subject, attempt and save directory
  - Select the appropriate task directory
  - Select the task and edit task parameters
  - Click `Ready` to initialize the task
  - Click `Start`
  - If you need to manually stop the task, Click `Stop`. Otherwise, the task will stop automatically.
  - To save data, click `Save Data`.
    - Data will be saved to: `<your save directory>/<subject>_YYYY-MM-DD_<attempt>.pickle`
  
To run another session, repeat the above steps. Data from the previous session is still loaded (and can be saved again with a different file name by changing the subject or attempt) until a new task is initialized (i.e. until you click `Ready`).
  
  

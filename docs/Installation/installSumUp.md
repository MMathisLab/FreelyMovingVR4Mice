
The FreelyMovingVR4Mice repository contains main **vr4mice** package (src code: teensyexp folder) and **mouse_task** module that is the input for **vr4mice**
# Installation

1. download source code

```
$ git clone git@github.com:MMathisLab/FreelyMovingVR4Mice.git
```
$ cd FreelyMovingVR4Mice (choose branch if needed)

1. create new conda environment with local pip:
```
$ conda create --name vr4mice python=3.9 pip
```
$ conda activate name_of_env
2. install *vr4mice* package  (_use pip install -e . if package is under development_)
```
$ pip install .
```
3. Note: it's possible to install **vr4mice** package directly from git:

```
$ pip install TODO(add repo's link)
```

## Getting Started

### Setting up your experimental system
#### Teensy 
  - Connect teensy microcontroller ([example of code to upload](../../mouse_task/teensy/teensy_AR.ino))
  - check rights on port access (modify via sudo chmod if needed)
#### Config files 
  - Set up the [config files](./Config_file_setup.md)
#### desktop icon
  -  How to create [desktop icon](./create_desktop_icon.md) using a .bat script (windows)





  
  

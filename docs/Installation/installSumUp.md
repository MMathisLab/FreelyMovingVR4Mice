
The FreelyMovingVR4Mice repository contains main **vr4mice** package (src code: teensyexp folder) and **mouse_task** module that is the input for **vr4mice**
# Installation

1. download source code

```
$ git clone git@github.com:MMathisLab/FreelyMovingVR4Mice.git
```
$ cd FreelyMovingVR4Mice (choose branch if needed)

1. create new conda environment with local pip:
```
$ conda create --name vr4mice python=3.7 pip
```
$ conda activate name_of_env
2. install *vr4mice* package  (_use pip install -e . if package is under development_)
```
$ pip install .
```


## Install DLCliveGUI
You will also need to install DLCliveGUI on a separate conda environment (call this environment dlclive_gui) you can find installation instructions on how to do this [here](https://github.com/DeepLabCut/DeepLabCut-live-GUI/blob/master/docs/install.md). However, you will want to use a tensorflow 2.x version since the model that we use for the tracking was made with tensorflow 2. Ensure that you also have the correct version of CUDA and cudnn installed on this conda environment for the tensorflow version that you are using.

you can then start the gui by typing ```dlclivegui``` when in the dlclive_gui environment.


## Getting Started

### Setting up your experimental system
#### Teensy 
  - Connect teensy microcontroller ([example of code to upload](../../mouse_task/teensy/teensy_AR.ino))
  - check rights on port access (modify via sudo chmod if needed)
#### Config files 
  - Set up the [config files](./Config_file_setup.md)
#### desktop icon
  -  How to create [desktop icon](./create_desktop_icon.md) using a .bat script (windows)





  
  

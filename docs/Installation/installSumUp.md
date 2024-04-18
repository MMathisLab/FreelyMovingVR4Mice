
The FreelyMovingVR4Mice repository contains main **vr4mice** package (src code: teensyexp folder) and **mouse_task** module that is the input for **vr4mice**
# Installation

1. Create a new conda environment with local pip:
	```
	conda create --name name_of_env python=3.10.12 pip
	```
	```
	conda activate name_of_env
	```
2. Download the [ml-agents repository](https://github.com/Unity-Technologies/ml-agents/tree/release_21) from Unity (_the `--branch release_21` option will switch to the tag of the latest stable release, which currently is **21** and is the one we use. Omitting that will get the main branch which is potentially unstable_):
	```
	git clone --branch release_21 https://github.com/Unity-Technologies/ml-agents.git
	```
	```
	cd ml-agents-release_21/
	```
	- Inside this main directory find the `ml-agents-envs/` sub-directory and open, with any text editor, the `setup.py` file found within it. Near the end of the file, find the list of required dependecies and modify the numpy version: change it from `"numpy==1.21.2"` to `"numpy==1.23.3"` then save. When that is done, run the following two commands in order:
		```
		python -m pip install ./ml-agents-envs
		```
		```
		python -m pip install ./ml-agents
		```
	- To check the installation was successful, run the following command:
		```
		mlagents-learn -h
		```
		This should print-out the manual on how to use the `mlagents-learn` command.

3. Finally go "up" one level (back to the location where you cloned the previous repository) and download the **vr4mice** source code:
	```
	git clone git@github.com:MMathisLab/FreelyMovingVR4Mice.git
	```
	```
	cd FreelyMovingVR4Mice
	```
	Choose a specific **branch** if needed by running:
	```
	git checkout branch_name
	```
	- install the **vr4mice** package  (_use `pip install -e .` if package is under development_):
		```
		pip install .
		```

## Install DLCliveGUI
DLClivegui handles reading from the camera and live pose estimation. Before installing DLClivegui you will need to install the correct drivers and C libraries for your camera. You can find links to these [here](https://github.com/DeepLabCut/DeepLabCut-live-GUI/blob/master/docs/camera_support.md). Make sure you add the C libraries to your system path if you are using a windows machine.

You will also need to install DLCliveGUI on a separate conda environment (call this environment dlclive_gui) you can find installation instructions on how to do this [here](https://github.com/DeepLabCut/DeepLabCut-live-GUI/blob/master/docs/install.md). However, you will want to use a tensorflow 2.x version since the model that we use for the tracking was made with tensorflow 2. Ensure that you also have the correct version of CUDA and cudnn installed on this conda environment for the tensorflow version that you are using.



you can then start the gui by typing `dlclivegui` when in the dlclive_gui environment.


## Getting Started

### Setting up your experimental system
#### Teensy 
  - Connect teensy microcontroller and upload the teensy sketch ([example of code to upload](https://github.com/MMathisLab/FreelyMovingVR4Mice/blob/main/mouse_task/teensy/teensy_AR.ino))
  - check rights on port access (modify via sudo chmod if needed)
#### Config files 
  - Set up the [config files](./Config_file_setup.md)
#### desktop icon
  -  How to create [desktop icon](./create_desktop_icon.md) using a .bat script (windows)





  
  

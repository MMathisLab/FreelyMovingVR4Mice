# FreelyMovingVR4mice overview

This documentation provides a user guide for the installation and getting an virtual/augmented reality system up and running. 
FreelyMovingVR4mice uses a collection of python packages developed within the Mathis lab, together these packages allow for the construction of a augmented reality. 
This "augmented reality" setup allows mice to interact with a unity game that is displayed on the screens around them.

## Hardware requirements

- Teensy 3.x board
- windows OS 10 or above
- GPU for DeepLabCut, with at least 8 GB of memory

## Software requirements

- Python3+ (tested on: 3.9)
- Unity3D (versions tested: 2019.3.2.f1)
- see `setup.py` for additional requirements


The augmented reality system runs on a python framework, this code was initially developed by Gary Kane, Michael Beauzile, and Mackenzie Mathis as a simple and scalable control suite for a host of systems neuroscience tasks. This was expanded with Sebastien Hausmann, Thomas Sainsbury and Jessy Lauer. This framework handles input and output to a teensy, parses actions to the Unity video game and handles all data logging for the experiments. In addition, it provides a simple GUI for the user to run the experiments and manually change parameters which control the experiments trial-like structure.

To run an augmented reality experiment, teensy experiments requires two objects:

1. A unity build that can be loaded - this is designed in unity in C#.  It uses the [Unity's mlagents-envs](https://github.com/Unity-Technologies/ml-agents) package (version: 1.14.1) such that actions can be received from python and so that game observations can be sent to python. The unity build that we have provided can be found within the mouse_task/unity_ar folder.

2. A python "teensy task" script - These are a class of scripts that can be loaded within the teensy experiments GUI and handle the organization of the task. In the case of FreelyMovingVR4mice these will be behavioral parameters calculated from DLClive keypoints coordinates. This script specifies what parameters will be sent to the game and the teensy throughout the experiment. These can be on a frame by frame, trial by trial or block by block basis. Currently, we provide two example teensy task scripts: The first script that reads from a movie of a mouse, this script can be used to test your installation of teensy experiments and a second script which runs on a incoming video stream from the camera. This second script can be modified as we come up with the final idea for the experiment and the training tasks!

These documents provide an explanation of how to use both of these objects is be provided within this documentation alongside an explanation of how to build the rig and installation.

This code was initially developed by Gary Kane, Michael Beauzile, and Mackenzie Mathis as a simple and scalable control suite for a host of systems neuroscience tasks. This was expanded with Sebastien Hausmann, Thomas Sainsbury and Jessy Lauer.


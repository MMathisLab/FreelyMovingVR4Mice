# DLCLive + Unity! (Under Construction)

This documentation provides a user guide for the installation and getting an virtual/augmented reality system up and running. 
DLClive + Unity uses a collection of python packages developed within the Mathis lab, together these packages allow for the construction of a augmented reality. 
This ``augmented reality" setup allows mice to interact with a unity game that is displayed on the screens around them.

## Hardware requirements

- Teensy 3.x board
- Windows OS (although it can work on Ubuntu)*
- GPU for DeepLabCut, with at least 8 GB of memory

## Software requirements

- Python3+ (tested on: 3.7)
- Unity3D (versions tested: 2019.3.2.f1)


The augmented reality system runs on a python framework, which was originally developed by G. Kane in the Adaptive Motor Control Lab. 
This framework handles input and output to a teensy, parses actions to the Unity video game and handles all data logging for the experiments. 
In addition, it provides a simple GUI for the user to run the experiments and manually change parameters which control the experiments trial-like structure.

To run an augmented reality experiment, teensy experiments requires two objects to be made:

1. A unity build that can be loaded - this is designed in unity in C#.  It uses the [Unity's mlagents-envs](https://github.com/Unity-Technologies/ml-agents) package (version: 1.14.1) such that actions can be received from python and so that game observations can be sent to python. 

2. A python "teensy task" script - this script sets up what types of actions will be sent to Unity. In the case of DLClive + Unity these will be behavioral parameters calculated from DLClive keypoint coordinates. 
3. It also specifies what parameters will be sent to the game and the teensy throughout the experiment. These can be on a frame by frame or trial by trial basis. 

An explanation of how to build both of these objects will be provided within this documentation page at a later date.

## Installation
To install all packages necessary for running the augmented reality software, first create a directory where you want this code to be installed and give it a name such as "DLClive_unity". Then `cd` into this directory and install the following packages using the steps below:


### teensy experiments
We recommend using a conda environment. If you haven't done so already, please install [anaconda](https://docs.anaconda.com/anaconda/install/). 
Next, run the following lines in a console:

1. Create a new conda environment. In this example, we'll name it `teensyexp`:<br/>
`conda create -n vr4mice python=3.7`

2. Activate the environment:<br/>
`conda activate teensyexp` or `source activate vr4mice`

3. clone the teensy_experiment package:<br/>
`git clone https://github.com/MMathisLab/FreelyMovingVR4Mice.git`

4. Enter the directory and pip install:
`pip install -e .`

This will install the package `teensyexp` with its dependencies (numpy, pyserial, [Unity's mlagents-envs](https://github.com/Unity-Technologies/ml-agents), opencv), and a script `teensy_experiment` to start TeensyExperiment directly from the console.


### Teensy Tasks
Whilst teensy experiments acts as an overall framework for running experiments using unity and a teensy it requires a python file called a "teensy task file". These files step up the task structure ie. what information should be send to the unity game on each trial, when the water command should be given to the teensy ect. This gives the experimenter control over experiment.
To download pre-made teensy tasks, use the following lines of code in the terminal from the DLCLive_unity folder:

WIP

 ### Installing DEEPLABCUT-Live and DLCLive GUI
 These DLC packages are also required to run the augmented reality setup. 
 Prior to installation of these DLC packages ensure that you have followed the the prerequisites required for DLC installation such as installing the relevant GPU drivers and  CUDA support for your GPU. 
 You can find information on how to do this [here](https://github.com/DeepLabCut/DeepLabCut/blob/master/docs/installation.md), just scroll down and follow the steps for GPU support. 
 Please note that if you are doing this on a lambda workstation this step may not be necessary, as all drivers and CUDA are preinstalled.

 To check that the NVIDIA GPU drivers are installed simply type `nvidia-smi` into your terminal. To check the CUDA version that is installed type `nvcc -V`.

Then to install DLC packages:
`pip install deeplabcut-live`

And then to also to read from a camera in real time you also want to install DLCLive GUI:
`pip install deeplabcut-live-gui`


### Add DLC model
Next you want add a DLC model to track an animal. 

WIP




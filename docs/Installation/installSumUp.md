# Installation

The FreelyMovingVR4Mice repository contains main **vr4mice** package (src code: teensyexp folder) and **mouse_task** module that is the input for **vr4mice**

_**Note:**_ _The following installation assumes you have already installed on your system the `conda` package manager. If you haven't, please follow the official installation process for Windows [here](https://docs.conda.io/projects/conda/en/stable/) (check [this](https://docs.anaconda.com/miniconda/) for more details)._

Create a new conda environment with local pip:

 ```bash
 conda create --name name_of_env python==3.10.12 pip
 ```

 ```bash
 conda activate name_of_env
 ```

Download our [forked ml-agents repository](https://github.com/AdaptiveMotorControlLab/ml-agents.git) from **AdaptiveMotorControlLab** (_the `--branch release_21_fix` option will switch to the tag of the latest stable "fixed" release, which currently is **21** and is the one we use. Omitting that will get the main branch_):

- Clone the repository:

  ```bash
  git clone --branch release_21_fix https://github.com/AdaptiveMotorControlLab/ml-agents.git
  ```

  ```bash
  cd ml-agents/
  ```

<!-- - Inside this main directory, find the `ml-agents-envs/` sub-directory and open, with any text editor, the `setup.py` file found within it. Near the end of the file, find the list of required dependencies and modify the `numpy` version: change it from `"numpy==1.21.2"` to `"numpy==1.23.3"` then save. When that is done, run the following two commands in order: -->

- Then, run the following two commands in order:

  ```bash
  python -m pip install ./ml-agents-envs
  ```

  ```bash
  python -m pip install ./ml-agents
  ```

- To check the installation was successful, run the following command:

  ```bash
  mlagents-learn -h
  ```

  This should print-out the **help** manual on how to use the `mlagents-learn` command.\
  >_Note: you can ignore WARNINGS related to PyTorch_

Finally go "up" one level (back to the location where you cloned the previous repository) and download the **vr4mice** source code:

- To return to previous folder from the command line you can run:

  ```bash
  cd ..
  ```

- Clone the FreelyMovingVR4Mice repository:

  ```bash
  git clone https://github.com/MMathisLab/FreelyMovingVR4Mice.git
  ```

  ```bash
  cd FreelyMovingVR4Mice
  ```

- Choose a specific **branch**, if needed, by running:

  ```bash
  git checkout branch_name
  ```

  > By default, the `main` branch  will be used.

- Install the **vr4mice** package  (_use `pip install -e .` if package is under development_):

  ```bash
  pip install .
  ```

- To check everything installed successfully (assuming no **ERRORS** were displayed in the process), try to run the following in your conda environment:

  ```bash
  vr4mice
  ```

🎉 **The GUI should appear on your screen!** 🎉

## Install DLCliveGUI

DLClivegui handles reading from the camera and live pose estimation. Before installing DLClivegui you will need to install the correct drivers and C libraries for your camera. You can find links to these [here](https://github.com/DeepLabCut/DeepLabCut-live-GUI/blob/master/docs/camera_support.md). Make sure you add the C libraries to your system path if you are using a windows machine.

You will also need to install DLCliveGUI on a separate conda environment (call this environment **dlclive_gui**) you can find installation instructions on how to do this [here](https://github.com/DeepLabCut/DeepLabCut-live-GUI/blob/master/docs/install.md). However, you will want to use a tensorflow 2.x version since the model that we use for the tracking was made with tensorflow 2. Ensure that you also have the correct version of CUDA and `cudnn` installed on this conda environment for the `tensorflow` version that you are using.

You can then start the gui by typing `dlclivegui` when in the **dlclive_gui** environment.

## Getting Started

### Setting up your experimental system

#### Teensy

- Connect teensy microcontroller and upload the teensy sketch ([example of code to upload](https://github.com/MMathisLab/FreelyMovingVR4Mice/blob/main/mouse_task/teensy/teensy_AR.ino))
- Check rights on port access (modify via `sudo chmod` if needed)

#### Config files

- Set up the [config files](./Config_file_setup.md)

#### Desktop icon

- How to create [desktop icon](./create_desktop_icon.md) using a `.bat` script (Windows)

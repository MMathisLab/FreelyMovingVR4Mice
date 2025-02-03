# Installation

The FreelyMovingVR4Mice repository contains main **vr4mice** package (src code: teensyexp folder) and **mouse_task** module that is the input for **vr4mice**

_**Note:**_ _The following installation assumes you have already installed on your system the `conda` package manager. If you haven't, please follow the [official installation tutorial for Windows](https://docs.conda.io/projects/conda/en/stable/) (check [this](https://docs.anaconda.com/miniconda/) for more details)._

Create and activate a new conda environment with local pip:

 ```bash
 conda create -n name_of_env python=3.10.12 && conda activate mlagents
 ```

Download and install **ml-agents**'s 22nd release directly from the repository:

- Clone the repository:

  ```bash
  git clone --branch release_22 https://github.com/Unity-Technologies/ml-agents.git
  ```

  ```bash
  cd ml-agents/
  ```

- Then, run the following command:

  ```bash
  python -m pip install ./ml-agents-envs
  ```

  > _Note: since we're using this library to interface with the Unity game from python, we only need the `ml-agents-envs` dependency. If you want to install the full package, you can additionally run the following command after the previous one:_
  >
  >```bash
  >python -m pip install ./ml-agents
  >```
  >
  > To verify that this additional installation was successful, you can try to run, in the conda environment created above, the following command:
  >
  >```bash
  > mlagents-learn --help
  >```
  >
  > If the installation was successful, the help manual of the `mlagents-learn` command should be displayed on your terminal window. For more details on how to install **ml-agents**, check the official documentation [here](https://unity-technologies.github.io/ml-agents/Installation/).

Now, it is necessary to go "up" one level (back to the location where the previous repository was cloned) and download the **vr4mice** source code:

- To return to previous folder from the command line, the following simple command can be used:

  ```bash
  cd ..
  ```

- To clone the FreelyMovingVR4Mice repository:

  ```bash
  git clone https://github.com/MMathisLab/FreelyMovingVR4Mice.git
  ```

  ```bash
  cd FreelyMovingVR4Mice
  ```

- Choosing a specific **branch**, if needed, can be done as follows:

  ```bash
  git checkout <name-of-the-branch>
  ```

  > _When cloning a Github repository, the default branch will usually be the `main` (or `master`)._

- To install the **vr4mice** package  (_use `pip install -e .` instead if planning to actively developing the package_):

  ```bash
  pip install .
  ```

- To check everything installed successfully (assuming no **ERRORS** were displayed in the process), try running the following in your conda environment:

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

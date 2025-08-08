# Installation

The FreelyMovingVR4Mice repository contains main **vr4mice** package (src code: teensyexp folder) and **mouse_task** module that is the input for **vr4mice**

_**Note:**_ _The following installation assumes you have already installed on your system the `conda` package manager. If you haven't, please follow the official installation process for Windows [here](https://docs.conda.io/projects/conda/en/stable/) (check [this](https://docs.anaconda.com/miniconda/) for more details)._

Create and activate a new conda environment with local pip:

 ```bash
 conda create -n <name-of-env> python=3.10.12 && conda activate <name-of-env>
 ```

 ```{hint}
 As an example, with `vr4mice_env` as the environment name, the above command would become as follows:
  ```bash
  conda create -n vr4mice_env python=3.10.12 && conda activate vr4mice_env
  ```

Now, it is necessary to clone the **FreelyMovingVR4Mice** repository and install the **vr4mice** package that comes with it:

- To clone the **FreelyMovingVR4Mice** repository:

  ```bash
  git clone https://github.com/MMathisLab/FreelyMovingVR4Mice.git
  ```

  ```bash
  cd FreelyMovingVR4Mice
  ```

- To choose a specific **branch** other than `main` or `master` (if needed):

  ```bash
  git checkout <name-of-the-branch>
  ```

  > _When cloning a GitHub repository, the default branch will usually be the `main` (or `master`)._

- To install the **vr4mice** package  (_use `pip install -e .` instead if planning to actively develop the package and modify the source code_):

  ```bash
  pip install .
  ```

To check everything installed successfully (assuming no **ERRORS** were displayed in the process), try to run the following in your conda environment:

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

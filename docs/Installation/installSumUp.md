# Installation

The FreelyMovingVR4Mice repository contains the main **vr4mice** package (the source code is in the `teensyexp/` sub-folder) and **mouse_task** module that is the input for **vr4mice**

```{warning}
The following installation assumes you have already installed on your system the `conda` package manager. If you haven't, please follow the [official installation tutorial](https://docs.anaconda.com/miniconda/install/) for the correct platform.
To be more specific, we will install `miniconda` which is a free, miniature installation of Anaconda Distribution that includes only conda, Python, the packages they both depend on, and a small number of other useful packages. See [this](https://docs.anaconda.com/miniconda/) for more information.
```

Create and activate a new conda environment with local pip:

 ```bash
 conda create -n <name-of-env> python=3.10.12 && conda activate <name-of-env>
 ```

 ```{hint}
 As an example, with `vr4mice_env` as the environment name, the above command would become as follows:
  ```bash
  conda create -n vr4mice_env python=3.10.12 && conda activate vr4mice_env
  ```

Download and install the **mlagents-envs** python package necessary for interfacing with the Unity game with python. To do so, run the following command:

```bash
python -m pip install mlagents-envs==1.1.0
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

- To check everything was installed successfully, run the following in your conda environment:

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

# Mouse task

## Dependencies

### Necessary packages

To run the tests, the following packages are required. They should already be available in the conda environment created when following the installation instructions [here](../Installation/installSumUp.md):

- `unittest`
- `tkinter`
- `pathlib`
- `numpy`

```{note}
These packages are already installed and available, thus there is no need to install them again.
```

### Optional packages

One of the testing scripts allows the user to manually test the game by moving the mouse cursor in a `pygame` window and to create artificial trajectories that can be later used to test the game automatically. For this, the following packages are required:

- `matplotlib`
- `pygame`

To install these, please navigate to the root folder of the repository (i.e. to `FreelyMovingVR4Mice/`), and run the following command:

  ```bash
  pip install -e .[testgen]
  ```

This will install the optional packages necessary for test generation as specified in the [setup.cfg file](../../setup.cfg)

## Overview

Some tests have been developed to ensure correct and consistent behavior of the game, more specifically on the **mouse_task** files, which represents the core of the game logic.

These tests can be found in the `FreelyMovingVR4Mice/mouse_task/tests/` folder.
The two mains files here are the following:

1. [test_mouse_active_sensing.py](../../mouse_task/tests/test_mouse_active_sensing.py): contains some unit tests for the main `ActiveSensingTask` class to make sure that core functionalities are working as intended.

2. [test_mouse_game_auto.py](../../mouse_task/tests/test_mouse_game_auto.py): leveraging the provided `test_trajectories.npy` file, this script can be used to automatically test the game by loading the numpy array and simulating the mouse's actions in the game. The code also performs additional tests to make sure that information about the state of the agent has the correct structure and contains valid values.

3. [test_mouse_game_manual.py](../../mouse_task/tests/test_mouse_game_manual.py): allows the user to manually test the `ActiveSensingTask` class through a pygame interface where the position inside the Unity game can be controlled by moving the cursor within the pygame window. To simplify things, trigger areas (such as the `TT` and `report` boxes) have been highlighted in green. This script also saves the traced trajectories of the mouse cursor in a numpy array (i.e., a `*.npy` file), which can be later loaded to automatically test the game with the `test_mouse_game_auto.py` script (below). When performing this manual testing, please run the script below as well as `test_mouse_game_auto.py` contains additional tests for data integrity and structure of the agent's state information.

```{note}
Since trials are randomly generated (i.e. the object can appear on either side of the arena with given probabilities), trials that were successful during manual testing (point `3.`) may not have the same outcome when performing automatic testing (point `2.`).

Since manual trajectories are already provided, **automatic testing should be preferred over manual testing**. If the creation of new trajectories is desired, the manual testing script can be used to do so.
```

## How to run tests

### Unit tests

To run the unit tests, simply run the corresponding python script, i.e. `test_mouse_active_sensing.py` in the `mouse_task/tests/` directory. To do so, you can execute the following command in your terminal:

```bash
python mouse_task/tests/test_mouse_active_sensing.py
```

```{warning}
 It is assumed that your terminal window is open at the root of the `FreelyMovingVR4Mice` repository and that the conda environment created [here](../Installation/installSumUp.md) is activated and has the necessary packages installed. If you are already in the `mouse_task/tests/` subfolder, you can directly run:

 ```bash
 python test_mouse_active_sensing.py
 ```

The unit tests contain several assertions that check crucial aspects of the game logic. Some of the tests include:

- testing that the object appears on the correct side based on the `prob_obj_on_left` attribute. Naturally, if `prob_obj_on_left = 1.0`, then the object will always appear on the left side and on the right side if `prob_obj_on_left = 0.0`. If the value is `0.5`, then the object will appear randomly on either side.
- testing whether trial blocks are correctly generated
- testing whether slit sizes are correctly calculated based on the list of values passed to the `task.get_slit_sizes([...])` class method.

### Game tests

#### General requirements

To run the game tests, you will need to have the Unity game executable file available. Once this taken care of, you'll be prompted to select the location of such file when running either the manual or automatic testing scripts.

#### Automatic

Leveraging the provided `test_trajectories.npy` file, the automatic testing script can be run to test the game. To do so, simply run the following command in an open terminal window:

```bash
python mouse_task/tests/test_mouse_game_auto.py
```

```{warning}
 It is assumed that your terminal window is open at the root of the `FreelyMovingVR4Mice` repository and that the conda environment created [here](../Installation/installSumUp.md) is activated and has the necessary packages installed. If you are already in the `mouse_task/tests/` subfolder, you can directly run:

 ```bash
 python test_mouse_game_auto.py
 ```

This script will load the numpy array file with the trajectories and simulate the mouse's actions in the game. The results will be printed in the terminal, showing whether each trial was successful or not.

#### [Optional] Manual

In order to manually test the game and/or generate a different set of manual trajectories to use in the automatic testing script, the following procedure can be followed. Run the corresponding python script in the `mouse_task/tests/` sub-folder. For instance, the python script can be run with the following command:

```bash
python mouse_task/tests/test_mouse_game_manual.py
```

```{warning}
 It is assumed that your terminal window is open at the root of the `FreelyMovingVR4Mice` repository and that the conda environment created [here](../Installation/installSumUp.md) is activated and has the necessary packages installed. If you are already in the `mouse_task/tests/` subfolder, you can directly run:

 ```bash
 python test_mouse_game_manual.py
 ```

By executing the above command (either one), you will first be prompted to select the location of the Unity game executable file, then the game will start and a pygame window will pop up as well. Here is a quick demonstration of the testing interface:

![interface](../images/testing_interface_720p.gif)

```{warning}
Since the game may boot up in full screen mode, you may have to resize the window to obtain a similar setup to the one shown above.
```

To exit the pygame and the game window, you just need to press the `ESC` key on your keyboard. After that, a matplotlib window will pop up displaying the different episode trajectories that have been "drawn" by the cursor during testing.
One important feature of the plot is that, at the end of each trajecotory, a green or red star has been added based on whether the "mouse" reported correctly or not respectively.

```{note}
The testing interface was designed such that it can be quit only during ITI. This means that pressing the `ESC` key just after reporting and before triggering a new trial is the only way to exit the game without any errors.
```

## How it works

All testing scripts make use of the **unit testing framework** that comes with the `unittest` python library. This allows to create test cases that can be run independently from each other and that can be easily extended as the codebase grows. It also allows the use of `mocks` and `patches` to modify or replace parts of the code for testing purposes. For instance, if we want to test a method of a python class that depends on another part of the code (e.g. an external function or another class method), we can "re-define" that part of the code only when running a test to make sure that the behavior of the third-party code does not affect the test results.

For the manual testing pipeline, a pygame interface was used to simulate the mouse moving in the arena with the camera and **DLC** live tracking. The user can easily move the cursor within the pygame window and the position will be interpolated to Unity arena coordinates and sent to the game. This is done by using a `patch` (as mentioned above) that replaces the `ActiveSensingTask`'s `get_action(...)` method which is responsible for getting the mouse's position from the **DLC Client** through the `_get_dlc_on_frame(...)` method. This way, the live tracking setup necessary on the rig can be easily bypassed for easier usability.

## Code currently missing tests

The testing framework is still early stage and will be continuously updated over time. Thus, some parts of the code logic still remain without unit tests, among which:

- the scripts under `./mouse_task/dlc_utils/`
- some of the game logic found in the python task scripts under `./mouse_task/`
- most of the scripts found under `./teensyexp/tasks_abc/`

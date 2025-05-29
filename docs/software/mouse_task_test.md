# Mouse task

## Necessary python packages

To run the tests, you will need to make sure that the following additional python packages are availabe in the conda environment you created when following the [installation instructions](../Installation/installSumUp.md):

- `matplotlib`
- `pygame`
- `pandas`

If any of these is missing, you can install it through:

```bash
python -m pip install <name-of-package>
```

or, more concisely, with:

```bash
pip install <name-of-package>
```

```{warning}
Other dependencies used in the tests, such as `unittest`, `pickle`, `tkinter`, `numpy`, and `pathlib` should already be included in the environment. If, by any chance, an error appears mentioning a missing dependency, you can install it with the above commands.
```

## Overview

Some tests have been developed to ensure correct and consistent behavior of the game, more specifically on the **mouse_task** files, which represents the core of the game logic.

These tests can be found in the `FreelyMovingVR4Mice/mouse_task/tests/` folder.
The two mains files here are the following:

1. [test_mouse_active_sensing.py](../../mouse_task/tests/test_mouse_active_sensing.py) : contains some unit tests for the main `ActiveSensingTask` class to make sure that core functionalities are working as intended.

2. [test_mouse_game_manual.py](../../mouse_task/tests/test_mouse_game_manual.py) : allows the user to manually test the `ActiveSensingTask` class through a pygame interface where the position inside the Unity game can be controlled by moving the cursor within the pygame window. To simplify things, trigger areas (such as the `TT`, and `report` boxes) have been highlighted in green. This script also saves the traced trajectories of the mouse cursor in a pickle file, which can be later loaded to automatically test the game with the `test_mouse_game_auto.py` script (below). When performing this manual testing, please run the script below as well as `test_mouse_game_auto.py` contains additional tests for data integrity and structure of the agent's state information.

3. [test_mouse_game_auto.py](../../mouse_task/tests/test_mouse_game_auto.py) : once a pickle file with manually generated trajectories is available, this script can be used to automatically test the game by loading the pickle file and simulating the mouse's actions in the game. The code also performs additional tests to make sure that information about the state of the agent has the correct structure and contains valid values.

```{note}
Obviously, since trials are randomly generated (i.e. the object can appear on either side of the arena with given probabilities), trials that were successful during manual testing (point `2.`) may not have the same outcome when performing automatic testing (point `3.`) since targets may appear on either side.

Manual testing should always be followed by automatic testing since, as mentioned above, the latter performs additional tests to ensure that the data structure of the agent's state information is correct. Autommatic testing, however, can be performed independently once the pickle file is available.
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

- testing that the object appears on the correct side based on the `prob_obj_on_left` attribute. Naturally, if `prob_obj_on_left = 1.0`, then the object will always appear on the left side and on the right side if `prob_
obj_on_left = 0.0`. If the value is `0.5`, then the object will appear randomly on either side.
- testing whether trial blocks are correctly generated
- testing whether slit sizes are correctly calculated based on the list of values passed to the `task.get_slit_sizes([...])` class method.

### Game tests

#### General requirements

To run the game tests, you will need to have the Unity game executable file available. Once this taken care of, you'll be prompted to select the location of such file when running either the manual or automatic testing scripts.

#### Manual

Performing manual testing of the game is similar to the above procedure, just run the corresponding python script in the `mouse_task/tests/` sub-folder. For instance, the python script can be run with:

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

#### Automatic

If a pickle file with trajectories (in the `mouse_task/tests` folder) is already available, the automatic testing script can be run instead. To do so, simply run the following command in an open terminal window:

```bash
python mouse_task/tests/test_mouse_game_auto.py
```

```{warning}
 It is assumed that your terminal window is open at the root of the `FreelyMovingVR4Mice` repository and that the conda environment created [here](../Installation/installSumUp.md) is activated and has the necessary packages installed. If you are already in the `mouse_task/tests/` subfolder, you can directly run:

 ```bash
 python test_mouse_game_auto.py
 ```

This script will load the pickle file with the trajectories and simulate the mouse's actions in the game. The results will be printed in the terminal, showing whether each trial was successful or not.

## How it works

All testing scripts make use of the **unit testing framework** that comes with the `unittest` python library. This allows to create test cases that can be run independently from each other and that can be easily extended as the codebase grows. It also allows the use of `mocks` and `patches` to modify or replace parts of the code for testing purposes. For instance, if we want to test a method of a python class that depends on another part of the code (e.g. an external function or another class method), we can "re-define" that part of the code only when running a test to make sure that the behavior of the third-party code does not affect the test results.

For the manual testing pipeline, a pygame interface was used to simulate the mouse moving in the arena with the camera and **DLC** live tracking. The user can easily move the cursor within the pygame window and the position will be interpolated to Unity arena coordinates and sent to the game. This is done by using a `patch` (as mentioned above) that replaces the `ActiveSensingTask`'s `get_action(...)` method which is responsible for getting the mouse's position from the **DLC Client** through the `_get_dlc_on_frame(...)` method. This way, the live tracking setup necessary on the rig can be easily bypassed for easier usability.

## Code currently missing tests

The testing framework is still early stage and will be continuously updated over time. Thus, some parts of the code logic still remain without unit tests, among which:

- the scripts under `./mouse_task/dlc_utils/`
- some of the game logic found in the python task scripts under `./mouse_task/`
- most of the scripts found under `./teensyexp/tasks_abc/`

<!-- TODO: add a python requirements.txt file for the testing suite. Maybe add how to install libraries from requirements file. I.e. pip install -r requirements.txt -->
<!-- ## Necessary python libraries

Here is a list of necessary libraries to run the above mentioned tests. Some of these, present by default in any python environment, were kept for sake of completeness:

- `pygame`
- `unittests`
- `pickle`
- `tkinter`
- `numpy`
- `pandas`
- `pathlib`
- `uuid`

If, when running the tests, an error appears mentioning a specific package is missing, this can be sovled (most of the time) but installing it through:

```bash
python -m pip install <name-of-package>
```

or, more concisely, with:

```bash
pip install <name-of-package>
``` -->

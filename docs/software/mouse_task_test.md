# Tests for the mouse task

As the **mouse_task** is represent the core of the game logic that mice are trained on, some tests have been developed to ensure the correct and consistent behavior of the game.

These tests can be found in the `FreelyMovingVR4Mice/mouse_task/tests/` folder.
The two mains files here are the following:

1. `test_mouse_active_sensing.py`: contains some unit tests for the main `ActiveSensingTask` to make sure that the main functionalities are working as intended.

2. `test_mouse_active_sensing_manual.py`: contains a script allowing the user to manually test the `ActiveSensingTask` through a pygame interface where the position inside the Unity game can be controlled by moving the cursor within the pygame window. To simply things, triggers areas (such as the `TT`, and `report` boxes) have been highlighted in green.

## How to run tests

### Unit tests

To run the unit tests, simply execute the script from the command line with the following command:

```bash
python mouse_task/tests/test_mouse_active_sensing.py
```

> _Note: here we assume you are currently located at the root of the `FreelyMovingVR4Mice` repository and that the conda environment that was created [here](../Installation/installSumUp.md) is activated and has the necessary packages installed. If you are already in the `tests` subfolder, you can simply run:_
>
> ```bash
> python test_mouse_active_sensing.py
> ```

The unit tests contain several assertions that check crucial aspects of the game logic. Some of the tests include:

- testing that the object appears on the correct side based on the `prob_obj_on_left` attribute. Naturally, if `prob_obj_on_left = 1.0`, then the object will always appear on the left side and on the right side if `prob_obj_on_left = 0.0`. If the value is `0.5`, then the object will appear randomly on either side.
- testing whether trial blocks are correctly generated
- testing whether slit sizes are correctly calculated based on the list of values passed to the `task.get_slit_sizes([...])` class method.

### Manual tests

Performing manual testing of the game is similar to the above procedure, just run the corresponding python script in the `tests` folder. For instance, you can run the following command in your open terminal window:

```bash
python mouse_task/tests/test_mouse_active_sensing_manual.py
```

> _Note: the same assumptions as above apply here. Again, if you are already in the `tests` folder (in your open terminal window), you can just run:_
>
>```bash
> python test_mouse_active_sensing_manual.py
>```

By executing the above command, you will first be prompted to select the location of the Unity game executable file, then the game will start and a pygame window will pop up as well. Here is a quick demonstration of the testing interface:

![interface](../images/testing_interface_720p.gif)

> _Note: since the game might boot up in full screen mode, you might need to resize the window to obtain a similar setup to the one shown above._

To exit the pygame and the game window, you just need to press the `ESC` key on your keyboard. After that, a matplotlib window will pop up displaying the different episode trajectories that have been "drawn" by the cursor during testing.
One important feature of the plot is that, at the end of each trajecotory, a green or red star has been added based on whethere the "mouse" reported correctly or not respectively.

## How it works

Both testing scripts, make use of the **unit testing framework** that comes with the `unittest` python library. This allows to create test cases that can be run independently from each other and that can be easily extended as the codebase grows. It also allows the use of `mocks` and `patches` to modify or replace parts of the code for testing purposes. For instance, if we want to test a method of a python class that depends on another part of the code (e.g. an external function or another class method), we can "re-define" that part of the code only when running a test to make sure that the behavior of the third-party code does not affect the test results.

For the manual testing pipeline, a pygame interface was used to simulate the mouse moving in the arena with the camera and **DLC** live tracking. The user can easily move the cursor within the pygame window and the position will be interpolated to Unity arena coordinates and sent to the game. This is done by using a `patch` (as mentioned above) that replaces the `ActiveSensingTask`'s `get_action(...)` method which is responsible for getting the mouse's position from the **DLC Client** through the `_get_dlc_on_frame(...)` method. This way, the live tracking setup necessary on the rig can be easily bypassed for easier usability.

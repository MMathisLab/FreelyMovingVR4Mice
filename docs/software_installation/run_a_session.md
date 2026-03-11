# Run a session

## Open the 2 GUIs
### VR4mice
In a terminal window, activate your conda environment where you installed the **vr4mice** package source code like this:
```
conda activate env_name
```
Then, to start a session, you can run:
```
vr4mice
```
Finally, the GUI that controls the experiment logic should appear!
Alternatively, you can add these commands to a .bat script so that all you need to do it click on an icon on your [Desktop](./create_desktop_icon.md).

### DeepLabCut-live
In a second terminal window, activate your conda environment where you installed the **dlclivegui** package source code just like you did above for the **vr4mice** environment.
Then, to start the GUI, you can run:
```
dlclivegui
```
This should open up the DLCLive GUI on your screen!

>_**Note:**_ close the program using the GUI's "**Stop**"/"**Close**" buttons, and **NOT** via "crtl-C"/"crtl-Z"

## Set up a session in the VR4mice GUI (aka Teensy Experiment)

```{image} ../../docs/images/run_session_steps_1-4.png
:alt: Steps 1 to 4
:width: 55%
:align: center
```

1) Select the desired configuration, the appropriate **Rig** and hit "**Connect**".
(_the name of the selected **Rig** should appear next to **Current Rig**_)
2) Select the **Subject**'s ID or name, the **Attempt** number and define the **Save Dir**ectory.
3) Select the wanted **Task Dir**ectory.
4) Define the **Task** and edit its parameters as needed.

## Open the DeepLabCut-live GUI


```{image} ../../docs/images/run_session_steps_5-9.png
:alt: Steps 5 to 9
:width: 55%
:align: center
```

5) Initialize the camera by clicking the "**Init Cam**" button.
(_a window should pop up with an a live video stream from the camera_)

6) Select the **Processor** file and hit "**Set Proc**" to load it.
7) Choose the **DeepLabCut** model that you are going to use from the dropdown list.
(_**DO NOT** hit **Init DLC** for now_)
8) Select the **Subject**'s name (or ID) and make sure it matches the one on the **vr4mice** GUI.
9) Hit "**Set Up Session**".
(_the **Ready** box below should turn blue_)

```{image} ../../docs/images/run_session_step_10.png
:alt: Step 10
:width: 95%
:align: center
```

```{tip}
Now, before initializing DLC, it would be a great time to take the selected mouse and put it gently (with tube handling) in the arena. Avoid forcing the mouse onto the platform, slowly approach with the tube and let the mouse naturally come out and into the arena.
```

10) Hit "**Init DLC**" and wait until the GPUs are loaded (look at the **terminal window**). DLCLive is now waiting for a socket with **vr4mice** GUI to be established.

## Launch OBS screen recording

Open **OBS** and start recording the screen (the screen where you are displaying the game on the rig). If you don't have **OBS** yet, check out [this link](https://obsproject.com/download) to download it. 
```{warning}
Make sure to set the recording **FPS** (frame rate per second) to **120**.
```

## On the VR4mice window

```{image} ../../docs/images/run_session_steps_11-12.png
:alt: Steps 11 and 12
:width: 55%
:align: center
```

11) Click on "**Ready**" to initialize the task and complete the socket.
12) Click on "**Start**".
(_if you need to manually stop the task, hit "**Stop**". Otherwise, the task will stop automatically_)
	> After the task started correctly, the bottom part of the panel should contain some information about the running session.

## On the DeepLabCut-live window

```{image} ../../docs/images/run_session_step_13.png
:alt: Step 13
:width: 95%
:align: center
```

13) Hit "**On**" to start recording video and DLC data.

## Saving data

The following steps have to be performed once the experimenter wants to end the session and save the recorded data (_they are the same steps even if the session was started by mistake or with the wrong configuration parameters and has to be stopped, the only difference will be in whether the data should be saved or not_).
Here the order is important, make sure to start with the **DeepLabCut-live** GUI followed by the **VR4mice** GUI and **OBS**.

### On the DeepLabCut-live window:

```{image} ../../docs/images/run_session_step_14.png
:alt: Step 14
:width: 95%
:align: center
```

14) Hit the Record "**Off**" button followed by "**Save Video**".
	> 4 different data types will be saved in the directory specified in the DLCLive-GUI:
	>	- `.avi` = the raw video
	>	- `_TS.npy` = the time steps for each of the recorded frames
	>	- `.h5` = the recorded DLC key-points
	>	- `PROC` = the processed dlc key-points which get sent to the unity game

### On the VR4mice window:

```{image} ../../docs/images/run_session_step_15.png
:alt: Step 15
:width: 55%
:align: center
```

15) To save the data, hit "**Stop**" followed by "**Save Task Data**".
	> _Data will be saved to: `<your save directory>/<subject>_YYYY-MM-DD_<attempt>.pkl` (pickle file)_

### Stop OBS screen recording

16) Last but not least, go back to **OBS** and stop the screen recording you started earlier. This will automatically save the video to a default path. Normally it should be in the current user's `Videos` folder. Make sure, after each session, to go to the aforementioned folder and rename the recorded video by inserting the name of the subject (i.e. mouse's name) at the beginning and the attempt number at the end. The naming convention used is `Name_Date_Attempt.*` (e.g. `Nightingale_2024-07-28_1.*`). The **Date** should already be present since it's automatically added by the **OBS** software.
	> _Note: the date will have US format._

To run another session, repeat the above steps. Data from the previous session is still loaded (and can be saved again with a different file name by changing the subject or attempt) until a new task is initialized (i.e. until you click "**Ready**").
Usually you'll need to run another mouse, thus meaning that **Subject Name** should be changed accordingly as well as the **Attempt**, which should be set back to 1 if not already. The task may also need to be changed since different mice may be at different training stages depending on the **continuation criteria** present in the [protocol](../training_protocols/training_protocol_tolias.md). After the new session parameters have been set, go back to **step 9** [here](#open-the-deeplabcut-live-gui) and repeat the steps from there.

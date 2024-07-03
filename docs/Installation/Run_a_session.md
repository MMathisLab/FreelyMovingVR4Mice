# How to run a session
Run: 

cd to the vr4mice directory and then:
```
$ vr4mice
```
and the gui that controls the experiment logic should appear!

Alternatively, you can add these commands to a .bat script so that all you need to do it click on an icon on your [desktop](./create_desktop_icon.md)

</br>_**Note:**_ close the program via gui via stop-close, and not via crtl-C/crtl-Z 
### In the VR4mice GUI

## set up a session in the VR4mice GUI
First:
  - Select your desired configuration
  - Select the appropriate teensy
  - Click `connect` to establish a serial connection with the microcontroller.

Next:
  - Select subject, attempt and save directory
  - Select the appropriate task directory
  - Select the task and edit task parameters

## Open DLCLive-GUI
 - In your DLClive conda environment type in `dlclivegui` into the terminal to open the DLC GUI
 - Initialize the camera by clicking the `Init_Cam` button (a window should pop up with an a live video stream from the camera)
 - select the `processor`file and click `set proc`
 - Choose the dlc model that you are going to use from the dropdown list
 - select the `subject name`
 - click setup `session button`
 - Then click the `init dlc`, and wait to see the GPUs load once this has loaded (you can see this in the terminal. DLClive is now waiting for a socket with the vr4mice gui to be established

## On the v4mice window
- Click `Ready` to initialize the task and complete the socket
- Click `Start`
- If you need to manually stop the task, Click `Stop`. Otherwise, the task will stop automatically.

## On the DLCLive-GUI window
- hit record `ON` - this will start recording the video and DLC data.


## Saving data
On the VR4mice window:
- To save data, click `Save Data`.
- Data will be saved to: `<your save directory>/<subject>_YYYY-MM-DD_<attempt>.pickle`

On the DLClive-gui window:
- hit the record `off` button followed by the `save video`button
- 3 different data types will be saved in the directory specified in the DLCLive-Gui:
  - `.avi` = the raw video
  - `_TS.npy` = the time steps for each of the recorded frames
  - `.h5` = the recorded DLC key-points
  - `PROC` = the processed dlc key-points which get sent to the unity game
  
To run another session, repeat the above steps. Data from the previous session is still loaded (and can be saved again with a different file name by changing the subject or attempt) until a new task is initialized (i.e. until you click `Ready`).

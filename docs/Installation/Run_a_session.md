# How to run a session
Run: 

cd to the vr4mice directory and then:
```
$ vr4mice
```
and the gui that controls the experiment logic should appear!

Alternatively, you can add these commands to a .bat script so that all you need to do it click on an icon on your [desktop](./create_desktop_icon.md)

</br>_**Note:**_ close the program via gui via stop-close, and not via crtl-C/crtl-Z 


### Interactions with gui

First:
  - Select your desired configuration
  - Select the appropriate teensy
  - Click `connect` to establish a serial connection with the microcontroller.

Next:
  - Select subject, attempt and save directory
  - Select the appropriate task directory
  - Select the task and edit task parameters
  - Click `Ready` to initialize the task
  - Click `Start`
  - If you need to manually stop the task, Click `Stop`. Otherwise, the task will stop automatically.
  - To save data, click `Save Data`.
    - Data will be saved to: `<your save directory>/<subject>_YYYY-MM-DD_<attempt>.pickle`
  
To run another session, repeat the above steps. Data from the previous session is still loaded (and can be saved again with a different file name by changing the subject or attempt) until a new task is initialized (i.e. until you click `Ready`).
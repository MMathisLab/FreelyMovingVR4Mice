### Getting Started

First, program your microcontroller according to the instructions [here](../example_teensy), and write tasks according to the instructions [here](tasks).

#### Setting up your experimental system
  - Create a new configuration file
  - Add new teensy. You will need to provide:
    - The serial port of the specific microcontroller (e.g. on windows, COM1)
    - The baud rate, specified in the [arduino sketch](../example_teensy)
    - List the inputs that are read from the microcontroller, separated by commas. For example, if you are reading the joystick x and y position and an IR beam break to monitor licking, this could be: `joystick_x, joystick_y, lick`
    - For each different command you would like to write to the microcontroller, click `Add Output`, and provide:
      - Name for the command (e.g. `water`)
      - The string character associated with the command (that you have coded into the arduino sketch; e.g. `W`)
      - Parameters for the command, separated by commas (e.g. `duration`)
  - Add subjects as desired
  - Select a directory to save your data (select `Browse` from the dropdown menu to add a new directory)
  - Select your task directory (instructions for organizing the task directory [here](tasks))
  
#### Running Experiments

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
  
  

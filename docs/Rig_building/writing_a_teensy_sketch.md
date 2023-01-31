# Writing Teensy sketch for Vr4mice

In Vr4mice, the microcontroller plays the role of reading and executing commands from the task (e.g. turn on the water valve), and writing data from sensors (e.g. encoders or IR beam breaks) back to the task. Please see the [template](../../mouse_task/teensy/teensy_AR.ino) for an example of what this should look like.

In general, the microcontroller will operate in one of two states: *task on* or *task off*. In the *task off* state, it will not write any data to the serial port, and it will wait for a *task on* command. In the *task_on* state, it will:
- Write data as sequences of 16-bit integers to the serial port at the desired sampling frequency, set by a constant `SAMPLE_RATE`. At frequencies > 250 Hz, the vr4mice program will occasionally lag behind by a few milliseconds. But for sampling rates up to 1000 Hz, it can catch up and will not lose any samples). Samples are delineated by a two number sequence: `-32767, 32767`.
- Read commands sent over the serial port. Commands are sent in the following fashion:
  - The first byte represents the command (use a letter, such as `W` for water delivery)
  - Followed by parameters for the command, such as the duration to turn on the water valve, sent as 16-bit integers.
  - (In task code, commands are sent by specifying the name of the command, followed by parameters. E.g., to deliver water for 100 ms: `teensy.write('water', [100])`
  
## Structure of the sketch
- At the top of the sketch, list important task constants. There should always be at least two: the baud rate (for serial communication with computer) and the sample rate (rate that teensy will write data to computer, in Hz). NOTE :: if using the [USB Serial on a Teensy board](https://www.pjrc.com/teensy/td_serial.html), the baud rate will always be 12mbit/s, no matter what you set here.
- Define the pin connections to the microcontroller.
- Initialize variables to control input/output. This will include a `task_on` and `last_print` variable to control writing to the serial port. For each command you wish to send to the microcontroller, we generally recomment a `command_on`, `command_start`, and `command_duration` variable.
- Define interrupts and the setup function. In the setup function, define pins as input or output (read vs. write), and attach interrupts to pins as needed.
- Define standard read and write functions for reading commands from and writing data to the serial port.
- Define the loop function: during execution, this function will be run continuously. It has three main sections:
  - If a command is available, read and execute (e.g. turn on water valve and record how long it should be on)
  - Check if any signals need to be turned off
  - If in the *task on* state, write data to the serial port.

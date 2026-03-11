# Configuring the teensy board and uploading the code

To configure your teensy board and be able to upload code to it you first need to download and install the open source [arduino IDE](https://www.arduino.cc/en/software). 
Then you need to specific Teensy loaders and drivers to do this follow this [tutorial](https://www.pjrc.com/teensy/first_use.html). 

To check everything works connect the teensy to the computer via the USB port and open the arduino IDE software and click on "tools/ports" and you should see that your teensy board is recognized and present on one of those ports.
Then open the teensy script which can be found at mouse_task/teensy/teensy_AR.ino in the arduino IDE. To compile this script click on the green tick within the arduino IDE. To upload this script to the teensy board you can then click on the green arrow button.

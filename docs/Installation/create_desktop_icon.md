# Create a desktop icon to launch Teensy experiments

Activating the vr4mice conda envrioment, moving to the code directory and launching the software from the terminal can be very time consuming, particularly when testing therefore we recommend creating a desktop icon that launches a .bat script. To do this, make a text file on your desktop and edit it in notepad and add in the following lines of code:

```bash
call activate vr4mice
cd "C:\Users\Windows\Documents\Mathis_lab_code\FreelyMovingVR4Mice\"
vr4mice
```

You will have to adjust the path after the cd to reflect the path to your cloned FreelyMovingVR4Mice repo.
Then save this file as 'vr4mice.bat' if you get an error saying that command prompt could not not find activate then follow this [tutorial](https://www.edureka.co/community/163047/conda-is-not-recognized-as-internal-or-external-command) to add conda to you computers system path. You should then be able to just click on this icon on your desktop to load the GUI!

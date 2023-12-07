![Screenshot from 2023-03-13 18-03-51](https://user-images.githubusercontent.com/43879378/234045182-c1e69d48-b6a2-4f76-b7f5-938bc3de840b.png)

`config.json` file contains all paths for local/remote directories for storage and transfer, as well as server IP and host name (without @). On Linux systems "localhost" can be  used for IP to test the system locally. All paths should be in Linux like format "/", and the application will manage paths according to the system.

#### The GUI consists of three modules: 

1. mouse information
2. experimental sessions information 
3. data transfer

More modules can be added. Each module corresponds to a Python class that implements an abstract template class.

#### Users can choose the mouse name from the mice drop-down menu to get the mouse relative information. 
Once a mouse is selected, all mouse-related module is updated, and the pre-selected option for other fields is uploaded from a cache .json file.
For transfer files user selects one file for transfer and an autocomplete function finds other files if the folder is known. 
The files can also affect the selected mouse, and the mouse name in the main section will be changed if the user agrees. 
 To add new files, the user must add new keys to the dictionaries in the transfer file. 
 
 #### Little zoom on code part:
 
Every class has dictionaries that define labels and names of keys from drop-down menus that create choices; fields can be modified or added via these dictionaries.
For each key in the "labels dictionary", a corresponding PyQt object is created, such as a text-field or combo-box. 
"Value dictionaries" with the same key as the label are linked to each PyQt object to access the information entered by the user. 
When the user presses the submit button, the "info dictionary" is filled, and any empty fields are tracked unless specified otherwise in the "special fields" dictionary. 
To create a new module, the user must implement a class similar to the ones for mice, experiments, and optogenetics, following the recommendations in the template code. 
It's crucial to keep the same names for tables and attributes in all dictionaries (labels, choices, etc.).
The transfer module has additional attributes to check the format of entered files and prevent rig-hosted files (video) from being added to the transfer queue. This module also pre-selects files and makes calls for updates if a new dataset is entered (file with new dataset selected). 
It's also possible to use only part of the implemented type files for transfer by specifying the desired keys in the transfer class constructor.
The gui.py script creates the main gui layer that will be completed with modules defied in the main script (entry point main.py). 
To modify existing modules, the user can play with keys in the dictionaries or attach functions to keys in the dictionary. The labels, options, primary keys, and special fields must be defined. ﻿

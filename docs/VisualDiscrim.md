---
jupytext:
  formats: md:myst
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---


# Active Sensing Task

In this task, a mouse the mouse looks through a slit in the wall and has to report which side an object of interest is on. This object of interest (OOI) randomly appears on the left or right side of the arena and is occluded by the slit. On the other side a distractor appears. The idea is that you have one script like this for each task type that you want to run. These task files are designed to control augmented reality games that have either trial like structure or trial-and-block structure (such as baseline, perturbation and washout trials). This current script can therefore be thought of as a template for future tasks that you want to employ. This document describes how the task is run and how to modify these scripts to build new tasks.


## Task active sensing outline - Outline
The python [class](https://github.com/MMathisLab/FreelyMovingVR4Mice/blob/main/mouse_task/task_active_sensing.py) acts as an interface between DLClive and the unity build and the teensy. This task can be imported in different task scripts such as [mouse_detection_p1.py](https://github.com/MMathisLab/FreelyMovingVR4Mice/blob/main/mouse_task/mouse_detection_p1.py) where the input parameters are changed for the different phases of training. These tasks then be selected from within the teensy experiments GUI using the task drop down menu. The parameters can also be manually edited by clicking clicking on the "edit" button. Here parameters such as reward size and the probability that the OOI will appear on the left can be set. This python script then logs all the data about the experiment such as the mouses position in the arena, when water was given and which side the mouse reported that the target was on. 

In takes the form of a parent class over a base class (called `unity_task`) and receives inputs within the `__init__()` function. These inputs can easily be modified from within the teensy experiments GUI by first loading the task and clicking on the edit button. This will present you with a window where these inputs can be modified. When the task is run (by clicking ready, followed by start) these inputs are assigned to class variables so that they can be made available to all the methods of the class.

There are four main functions within the script that control different aspects of the game:

1. `set_channel()` - this is called at the beginning of each trial and can be used to send parameters to the unity game.
2. `get_action()` - this function is called on every frame and its output is sent as "actions" to the unity game. In our case of wanting to use a freely moving animal to control the game this function calls another function that reads the DLC data from a socket which the DLCliveGUI is sending data to. Currently, this data is the animals x,y positions and its heading angle. These coordinates from the images are then mapped to game coordinates and sent to the unity game to control the game cameras, changing how the environment is rendered on the screens.
3. `check_reward()` - this function is called on every frame and checks if a reward has been given within the unity game. If it has the function sends a command to the teensy to deliver a water reward.
4. `get_data()` - this function is called when the "save task data" button within the GUI is pressed at the end of an experiment. This saves the data into a pickle file with the mouse_name that is defined in the GUI, followed by the data and the attempt (**Dodo_170722_1.pkl**)
If you want to modify the task handling you can edit the code within these functions to change how the task runs.


### GUI Parameters

Here is an explanation of the parameters that can be set in the GUI. Such parameters can either be used to control aspects of the game that need to be sent to the teensy such as reward size. Or these parameters can be sent to the unity game on a trial by trial basis to control the unity game parameters:


```{code-cell} ipython3
:tags: [mytag]

    def __init__(
        self,
        teensy,
        monitor=None,
        write_video=False,
        fps=60.0,
        session_label=["ar_detection_no_velthr"],
        epochs=[250],
        epoch_labels=["single_teardrop"],
        config_file_path=config_path,
        reward_size=100,
        cropped_image=[0, 530, 0, 510],
        unity_arena_size=[-9, 9, -10, -2],
        r_report_box=[5, 10, -4, -2],
        l_report_box=[-10, -5, -4, -2],
        start_box=[-4, 4, -9, -5, 90],
        rotate_camera=90.0,
        prob_obj_on_left=0.5,
        prob_block_coherence = 0.5,
        mouse_report_delay=0.0,
        slit_size=[4.0, 4.0, 1],
        slit_depth=0.2,
        target_selection=6.0,
        distractor_selection=4.0,
        occlusion_type=0.0,
        camera_type=1.0,
        target_spread=4.0,
        target_rotation=0,
        target_size=2.0,
        target_height=3.0,
        block_length=1.0,
        start_box_delay=0.1,
        velocity_threshold=20.0,
        distractor=0.0,
        grey_screen_active=0.0,
        target_distance=3,
        use_dlc=True)
```


1. `teensy`: Teensy object, instance of teensy class that controls the teensy microcontroller.
2. `monitor`: Not used.
3. `write_video`: Boolean, default is `False`. If `True`, video output will be recorded.
4. `fps`: Float, frames per second for recorded video (default is `60.0`, **currently not used**).
5. `session_label`: List, contains the name of the task type (This will change depending on which training task is imported`).
6. `epochs`: List, contains the number of epochs (or trials) (default is `[250]`).
7. `epoch_labels`: List, contains epoch labels or names of the blocks, Single teardrop is default and highlights that only one tear drop is shown to the animal.
8. `config_file_path`: Path object, path to the configuration **.json** file (see `helpers.py` for more information).
9. `reward_size`: Integer, This specifies how may ms the water valve should be open for. This should be adjusted such that the reward given is approximately **3µL** (default is `100`).
10. `cropped_image`: List, contains the dimensions of the cropped image (default is `[0, 530, 0, 510]` - [left, right, top, bottom]).
11. `unity_arena_size`: List, contains the dimensions of the Unity arena (default is `[-9, 9, -10, -2]` - [left, right, top, bottom]).
12. `r_report_box`: List, contains the dimensions of the right report box (default is `[5, 10, -4, -2]` - [left, right, top, bottom]).
13. `l_report_box`: List, contains the dimensions of the left report box (default is `[-10, -5, -4, -2]` - [left, right, top, bottom]).
14. `start_box`: List, contains the dimensions of the start box and its angle (default is `[-4, 4, -7, -3, 80]` - [left, right, top, bottom, angle], here angle refers to the fact that the animal must be looking at the screen within +- the angle).
15. `rotate_camera`: Integer, rotation angle of the camera (default is `90`). This needs to be adjusted to your rig and then not changed.
16. `prop_obj_on_Left`: Float, probability of the OOI being on the left side (default is `0.5`). This parameter is used if the block length is set to 1, if the block length is > 1 then prob block coherence is used.
17. `prob_block_coherence`: Float, this is the probability that the OOI will appear on the same side as the block. ie if the block was a left block and the prob_block_coherence was 1 then it would appear on the left (default is 0.5). This parameter is only used if the block length is greater that 1.
17. `mouse_report_delay`: Float, mouse report delay default is `0`.
18. `slit_size`= List, this is a list of numbers [min_slit_size, max_slit_size, number_of_slit_sizes] ie. [10,20,5] would give a range of 5 slit sizes with 10 being the minimum and 20 being the max.
19. `slit_depth`= Float, this parameter controls the depth or thickness of the walls (default = 0.2)
20. `target_selection`: Integer, this parameter selects what object for the OOI (`0.` = white cube, `1.` = black cube, `2.` = teardrop grey, `3.` = pacman grey, `4.` = teardrop black, `5.` = pacman black, `6.` = teardrop white, `7.` = pacman white,`8.`= zebra teardrop, `9.`= zebra ball, `10.`=white ball, `11.`=light gray zebra teardrop, `12.` = dark gray zebra teardrop )
21. `distractor_selection`: Integer, this parameter selects what object for the distractor (`0.` = white cube, `1.` = black cube, `2.` = teardrop grey, `3.` = pacman grey, `4.` = teardrop black, `5.` = pacman black, `6.` = teardrop white, `7.` = pacman white,`8.`= zebra teardrop, `9.`= zebra ball, `10.`=white ball, `11.`=light gray zebra teardrop, `12.` = dark gray zebra teardrop )
22. `occlusion_type`: Integer, allows the user to select the type of occlusion that they want to use. (`0` = no occlusion, `1` = slit occlusion, `2` = central wall), default is no occlusion.
23.  `camera_type`: Integer, allows the user to select between on (Camera_type = `0`) and off axis camera (Camera_type = `1`) modes.
24. `target_spread`: Float, specifies the distance between the targets.
25. `target_rotation`: Float, altering this parameter causes the tips of the targets to be rotated inward making them easier for the animal to see. 
25. `target_size`: Integer, specifies the size of the targets i recommend using size `1` for the teardrop and double teardrop.
26. `target_height`: Float, specifies the height at which the targets are spawned.
27. `block_length`: Float, specifies how many rewards the mouse has to get correct before the OOI switches sides. To enforce this make sure that you have the prop_object_on left parameter set to `1.0`. If prob_object_on_left is set to `.5` then this block length parameter has no effect as there is a 50% chance of the object appearing on the each side.
26. `start_box_delay`: Float, specifies the time that the animal needs to spend in the start box under the velocity threshold.
27. `velocity_threshold`: Float, the animal must be below this value in the start box for a trial to be initiated.
27. `distractor`: Integer, specifies whether the distractor is present or not. (`0` = no distractor, `1` = distractor)
28. `grey_screen_active`: Integer, specifies whether to show the grey ITI screen or not (`0` = no grey screen, `1` = grey screen)
29.  `target_distance`: Integer, specifies the distance of the targets in y.
30. ` use_dlc`: Bool, specifies whether to use the dlc socket or not, this is mainly used for debugging, it should be set to true for the task to run.


#### Adding new game parameters
New parameters can be added to this task by placing them within the arguments of the class init shown above.
If you want to send these parameters to the teensy you can use the [write function](../teensyexp/teensy.py).
For example see the [check_reward](../mouse_task/mouse_ar_task.py) function below. This function gets input from the unity game on every frame in the form of a binary vector where 0 represents no reward and 1 represents a time frame when the reward was given. When this reward vector is above zero the function sends a command to the water pin on the teensy, telling it to open the valve for a set number of ms: 

```{code-cell} ipython3
:tags: [check_reward]

def check_reward(self):
        """
        Set up the reward.
        """
        if self.reward > 0:
            self.correct += 1

            if self.state[7] > 0:
                print("___ Rewarded - left ___")
                print(self.reward_size)
                self.teensy.write("l_water", [self.reward_size[0]])
            else:
                print("___ Rewarded - right ___")
                print(self.reward_size)
                self.teensy.write("r_water", [self.reward_size[0]])
            self.n_rewards += 1
```


Alternatively, parameters can also be sent the unity game and the beginning of the each trail to set up various features of the game, this can be done by adding them as a "side channel" in the [set_channel](mouse_task/mouse_ar_task.py) function:

```{code-cell} ipython3
:tags: [set_channel]
def set_channel(self):
        """
        Send parameters to unity when the game is reset i.e. at the beginning of each trial

        Method inherited from task parent class interface.

        Note: can use this function to save data to the .pickle file and send parameters to unity
        """

        if self.block_length == 1:
            self.random_target_location()
        if self.block_length > 1:
            self.block_sampler()

        this_prob_obj_left = self.prob_obj_on_left
        print("prob left", this_prob_obj_left)
        this_slit_size = np.random.choice(self.slit_sizes)
        print("slit_size", this_slit_size)
        this_slit_depth = self.get_epoch_value("slit_depth")
        this_target_spread = self.get_epoch_value("target_spread")
        this_target_height = self.get_epoch_value("target_height")
        this_mouse_report_delay = self.get_epoch_value("mouse_report_delay")
        this_target_selection = self.get_epoch_value("target_selection")
        this_distractor_selection = self.get_epoch_value("distractor_selection")
        this_occlusion_type = 0.0  # self.get_epoch_value("occlusion_type")
        this_target_distance = self.get_epoch_value("target_distance")
        this_target_rotation = self.get_epoch_value("target_rotation")

        self.channel.set_float_parameter("cameraSelection", self.camera_type)
        self.channel.set_float_parameter("target_selection", this_target_selection)
        self.channel.set_float_parameter(
            "distractor_selection", this_distractor_selection
        )
        self.channel.set_float_parameter("object_on_left", self.object_on_left)
        self.channel.set_float_parameter("slitSize", this_slit_size)
        self.channel.set_float_parameter("slit_depth", this_slit_depth)
        self.channel.set_float_parameter("targetsFromMidline", this_target_spread)
        self.channel.set_float_parameter("targetsheight", this_target_height)
        self.channel.set_float_parameter("mouseReportDelay", this_mouse_report_delay)
        self.channel.set_float_parameter("startBoxDelay", self.start_box_delay)
        self.channel.set_float_parameter("velocityThreshold", self.velocity_threshold)
        self.channel.set_float_parameter("occlusion_type", this_occlusion_type)
        self.channel.set_float_parameter("targetsZpos", this_target_distance)
        self.channel.set_float_parameter("target_rotation", this_target_rotation)
        print("this occ_type: ", this_occlusion_type)

        # set properties for start box, left report box and right report box
        self.channel.set_float_parameter("L_box_x_min", self.l_report_box[0])
        self.channel.set_float_parameter("L_box_x_max", self.l_report_box[1])
        self.channel.set_float_parameter("L_box_z_min", self.l_report_box[2])
        self.channel.set_float_parameter("L_box_z_max", self.l_report_box[3])

        self.channel.set_float_parameter("R_box_x_min", self.r_report_box[0])
        self.channel.set_float_parameter("R_box_x_max", self.r_report_box[1])
        self.channel.set_float_parameter("R_box_z_min", self.r_report_box[2])
        self.channel.set_float_parameter("R_box_z_max", self.r_report_box[3])

        self.channel.set_float_parameter("TT_box_x_min", self.start_box[0])
        self.channel.set_float_parameter("TT_box_x_max", self.start_box[1])
        self.channel.set_float_parameter("TT_box_z_min", self.start_box[2])
        self.channel.set_float_parameter("TT_box_z_max", self.start_box[3])
        self.channel.set_float_parameter("TT_box_angle", self.start_box[4])
        self.channel.set_float_parameter("distractor", self.distractor)
        self.channel.set_float_parameter("targetSize", self.target_size)
        self.channel.set_float_parameter("Grey_screen_active", self.grey_screen_active)

        # add trial parameters to trial vectors so that we can save them to the log file
        self.trial_epoch_labels.append(self.get_epoch_value("epoch_labels"))
        self.trial_slit_size.append(this_slit_size)
        self.trial_slit_depth.append(this_slit_depth)
        self.trial_target_spread.append(this_target_spread)
        self.trial_slit_depth.append(this_slit_depth)
        self.trial_target_height.append(this_target_height)
        self.trial_mouse_report_delay.append(this_mouse_report_delay)
        self.trial_distractor_selection.append(this_distractor_selection)
        self.trial_target_selection.append(this_target_selection)
        self.trial_occlusion_type.append(this_occlusion_type)
        print(self.trial_occlusion_type)
        self.trial_target_distance.append(this_target_distance)
        self.trial_target_rotation.append(this_target_rotation)
```

In this function, first the parameter for the current trial is extracted by `self.get_epoch_value()`. In this example script, we have no block like structure ie. each trial uses the same parameters, so for each trial the parameters are identical for all `250` trials. If you want to add block like structure see the "adding block structure" section below. The function, after getting the parameters for this trial, then sends them to unity using the `self.channel.set_float_parameter()` function. In the unity game there is a similar C# function which is waiting for these parameters so the string that is parsed has to be identical to how they are defined in the unity game. Finally, this function appends a vector which represents what the parameter was for each trail within the whole session, these vectors can then be saved in the `get_data()` function at the end of the script. 

### Reading poses from DLC live
In the augmented reality setup actions are sent from the DLCliveGUI via a socket to the computers localhost these can be read within the python task script using the [DLCClient class](https://github.com/MMathisLab/FreelyMovingVR4Mice/blob/main/teensyexp/tasks_abc/dlc_socket.py). This class gets initialized when the task script is loaded, and begins to read from the socket on a thread. 

```{code-cell} ipython3
:tags: [read on thread]
    self.address = ('localhost', 6000)
    self.dlcClient = DLCClient(address=self.address)
```

We can then read from this thread periodically and send the data to unity by the `dlcClient.read()` method. In the python task script this is called within the `_get_dlc_on_frame()` function. This function adds the incoming data to vectors which can be saved at the end of the experiment. It also maps the dlc data (which is in pixel coordinates from the camera images) to unity coordinates. 

```{code-cell} ipython3
:tags: [_get_dlc_on_frame]
    
    def _get_dlc_on_frame(self):
        """
        Runs DLC on every frame.

        It is used in ``get_action()``, called by teensyexp's module Agent.
        This is run on every frame after the dlc processor is initialized.
        """

        # run DLC on every frame to be given as input to the agent
        this_read = self.dlcClient.read()

        # check whether there is incomming data in the read
        if this_read != None:
            self.params = np.array(this_read["vals"][1:])
            # filter the data points
            if self.t_count == 0:
                self.filt = OneEuroFilter(
                    t0=self.t_count,
                    x0=np.array(self.params),
                    beta=0.01,
                    min_cutoff=0.01,
                )
            else:
                self.params = self.filt(self.t_count, np.array(self.params))
            self.t_count = self.t_count + 1
            x = self.params[0]
            z = self.params[1]
            head_angle = self.params[2]

            # read the photodiode value
            photodiode_intensity = np.array(this_read["vals"])[-1]
            self.dlc_x.append(x)
            self.dlc_y.append(z)
            self.dlc_heading.append(head_angle)
            self.dlc_read_time.append(this_read["time"])

            # interp mouse pixel space into arena space
            x = np.interp(
                x,
                [self.cropped_image[0], self.cropped_image[1]],
                [self.unity_arena_size[0], self.unity_arena_size[1]],
            )
            z = np.interp(
                z,
                [self.cropped_image[2], self.cropped_image[3]],
                [self.unity_arena_size[2], self.unity_arena_size[3]],
            )
            self.degrees = (head_angle - (self.rotate_camera)) % 360
            output = np.array([x, z, self.degrees, photodiode_intensity])
            self.previous = output
        else:
            # print("missed dlc frame")
            time.sleep(0)
            output = self.previous
        return output.reshape((1, -1))

```
Finally, this function gets called by the `get_action()`function. This function gets called every time the unity game is ready for action. 


#### get action function 
```{code-cell} ipython3
:tags: [get_action]
    def get_action(self):
        """
        Get actions from DLC and parse them to unity.

        Called by teensyexp's module Agent.
        This function is called on every frame of the game.
        """
        if self.use_dlc == False:
            output = self.previous
        else:
            output = self._get_dlc_on_frame()
        return output

```
This takes the incomming data stream from dlclivegui and sends the processed data to the unity game



#### Data saving functionality
At the end of the experiment, we want to save various forms of data such as trial by trial parameters and frame by frame actions that the animal took. This can be done by creating lists that can be appended with these parameters either when a trial begins or on each frame of the game. These can then all be saved into a **.pkl** file by the `get_data()` function in the python task file. Data gets saved by then clicking the save data button within the **vr4mice GUI**.


#### Adding block like structure
In addition, to the parameters being identical across trials we may also like to add block like structure such as a baseline and perturbation block. An example of this could be the visual discrimination task without occluders for the first `100` trial followed by `100` trials with occulders. This can be achieved by passing the parameters to the class as lists:


```{code-cell} ipython3
:tags: [set_channel]
def __init__(self, teensy, monitor=None, write_video=False, fps=60.0, cropped_image = [55,610,55,455], rotate_camera = [270],
                 epochs=[100,100], epoch_labels = ["baseline", "occluded"],
                 config_file_path = config_path,
                 reward_size = [45,45],  Prop_Obj_on_Left = [0.5,0.5], 
                 slit_size = [10,2], slit_depth = [2,2], target_spread = [4,4]):
```

Here we have modified the blocks to have `100` trial each by specifying that `epochs = [100,100]`. We have then named these blocks using `epoch_lables = ["baseline", "occluded"]`. Then the only parameter that changes between these two blocks is the size of the slit that the mouse has to look through to see the targets. in the first block this is set to be `10` (the slit is so wide that the objects are unoccluded) where as in the second block the slit size is much lower (`slit_size = 2`). Under this framework if we call the `self.get_epoch_value()` the first element in the list is returned if the trial number is less than `100` but if it is more than `100` then the second element in the parameter list is returned. 

Being able to change the parameters in this way allows the user to have control over the task structure and the aesthetics of the game from the GUI






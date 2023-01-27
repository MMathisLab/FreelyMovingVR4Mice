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


# Augmented reality visual discrimination task

In this task, a mouse the mouse looks through a slit in the wall and has to report which side an object of interest is on. This object of interest (a green cube) randomly appears on the left or right side of the arena and is occluded by the slit. On the other side a blue cube appears. The idea is that you have one script like this for each task type that you want to run. These task files are designed to control augmented reality games that have either trial like structure or trial-and-block structure (such as baseline, perturbation and washout trials). This current script can therefore be thought of as a template for future tasks that you want to employ. This document describes how the task is run and how to modify these scripts to build new tasks.


## Python "Task" script - Outline
The python [task](https://github.com/MMathisLab/FreelyMovingVR4Mice/blob/mary/demo/mouse_task/mouse_ar_task.py) acts as an interface between DLClive and the unity [build](https://github.com/MMathisLab/FreelyMovingVR4Mice/tree/mary/demo/mouse_task/unity_ar) and the teensy. It can be selected from within the teensy experiments GUI by clicking on the "edit" button one the task have been selected from the dropdown menu. Here parameters such as reward size and the probability that the cube will appear on the left can be set. This python script then logs all the data about the experiment such as the mouses position in the arena, when water was given and which side the mouse reported that the target was on. 

In takes the form of a parent class over a base class (called unity_task) and receives inputs within the __init__() function. These inputs can easily be modified from within the teensy experiments GUI by first loading the task and clicking on the edit button. This will present you with a window where these inputs can be modified. When the task is run (by clicking ready, followed by start) these inputs are assigned to class variables so that they can be made available to all the methods of the class.

There are four main functions within the script that control different aspects of the game:

1. set_channel() - this is called at the beginning of each trail and can be used to send parameters to the unity game.
2. get_action() - this function is called on every frame and its output is sent as "actions" to the unity game. In our case of wanting to use a freely moving animal to control the game this function runs a DLClive processor on the incoming video stream from the behavioral cameras to extract out the animals x,y positions and its heading angle. These coordinates from the images are then mapped to game coordinates and sent to the unity game to control the game cameras, changing how the environment is rendered on the screens.
3. check_reward() - this function is called on every frame and checks if a reward has been given within the unity game. If it has the function sends a command to the teensy to deliver a water reward.
4. get_data() - this function is called when the "save task data" button within the GUI is pressed at the end of an experiment. This saves the data into a pickle file with the mouse_name that is defined in the GUI, followed by the data and the attempt (Dodo_170722_1.pkl)

If you want to modify the task handling you can edit the code within these functions to change how the task runs.


### Gui Parameters

Here is an explanation of the parameters that can be set in the GUI:

1. reward_size -  This specifies how may ms the water valve should be open for
2. Prop_Obj_on_Left -  probability that the object of interest (green cube) will appear on the left
3. cropped_image - The pixel dimensions of the image of the box that the mouse walking around in [left, right, top, bottom] all dimensions are in pixels. These are then mapped to the game space and sent to unity to control.

such parameters can either be used to control aspects of the game that need to be sent to the teensy such as reward size. Or these parameters can be sent to the unity game on a trial by trial basis to control the unity game parameters.


#### Adding new game parameters
New parameters can be added to this task by placing them within the arguments of this class, as done with the "new_param" in the code cell below. These parameters will automatically appear in the GUI when you click on the edit button. 

```{code-cell} ipython3
:tags: [mytag]

def __init__(self, teensy, monitor=None, write_video=False, fps=60.0,
                cropped_image = [55,610,55,455], rotate_camera = 270,
                epochs=[250], epoch_labels = ["baseline"],
                config_file_path = config_path,
                reward_size = 45, Prop_Obj_on_Left = 0.5, 
                slit_size = 2, slit_depth = 2, target_spread = 4):
```

If you want to send these parameters to the teensy you can use the [write function](../teensyexp/teensy.py).
For example see the [check_reward](../mouse_task/mouse_ar_task.py) function below. This function gets input from the unity game on every frame in the form of a binary vector where 0 represents no reward and 1 represents a time frame when the reward was given. When this reward vector is above zero the function sends a command to the water pin on the teensy, telling it to open the valve for a set number of ms: 

```{code-cell} ipython3
:tags: [check_reward]

def check_reward(self):
        """
            method to set up the reward
        """
        if self.reward > 0:
            print("___ Rewarded ___")
            print(self.reward_size)
            self.teensy.write('water', [self.reward_size]) 
            self.n_rewards += 1
```


Alternatively, parameters can also be sent the unity game and the beginning of the each trail to set up various features of the game, this can be done by adding them as a "side channel" in the [set_channel](mouse_task/mouse_ar_task.py) function:

```{code-cell} ipython3
:tags: [set_channel]
def set_channel(self):
        """
            method inherited from task parent class interface
            This function sends parameters to unity when the game is reset - ie at the beginning of each trial
        """

        # extract parameters for the current trial using self.get_epoch_value()
        this_Prob_obj_left = self.get_epoch_value("Prob_Obj_on_Left")
        this_slit_size = self.get_epoch_value("slit_size")
        this_slit_depth = self.get_epoch_value("slit_depth")

        # send the parameters to unity 
        self.channel.set_property("Prob_Obj_on_Left", this_Prob_obj_left)
        self.channel.set_property("slit_size", this_slit_size)
        self.channel.set_property("slit_depth", this_slit_depth)

        # add trial parameters to trial vectors so that we can save them to the log file
        self.trial_epoch_labels.append(self.get_epoch_value("epoch_labels"))
        self.trial_split_size.append(this_slit_size)
        self.trial_split_depth.append(this_slit_depth)
```

In this function, first the parameter for the current trial is extracted by self.get_epoch_value(). In this example script, we have no block like structure ie. each trial uses the same parameters, so for each trial the parameters are identical for all 250 trials. If you want to add block like structure see the "adding block structure" section below. The function, after getting the parameters for this trial, then sends them to unity using the self.channel.set_property() function. In the unity game there is a similar c# function which is waiting for these parameters so the string that is parsed has to be identical to how they are defined in the unity game. Finally, this function appends a vector which represents what the parameter was for each trail within the whole session, these vectors can then be saved in the get_data() function at the end of the script. 



```{code-cell} ipython3
:tags: [get_action]
    def get_action(self):
        """
            method that get actions from DLC and parse them to unity
            called by teensyexp's module Agent, This function is called on every frame of the game.
        """
        data = self.queue.read(position='last', clear=False)
        if data is None:
            return np.array([0, 0, 0]).reshape((1, -1))
        
        x = data[0]
        z = data[1]
        head_angle = data[2]


        # interp mouse pixel space into arena space
        x = np.interp(x,[55,610], [-6,6])
        z = np.interp(z,[55,610], [-4,-15])
        degrees = (head_angle - (90+180)) % 360; 
        output = np.array([x,z,degrees])
        print(output)
        return(output.reshape((1,-1)))

```

#### Adding block like structure
In addition, to the parameters being identical across trials we may also like to add block like structure such as a baseline and pertubation block. An example of this could be the visual discrimination task without occluders for the first 100 trial followed by 100 trials with occulders. This can be achieved by passing the parameters to the class as lists:


```{code-cell} ipython3
:tags: [set_channel]
def __init__(self, teensy, monitor=None, write_video=False, fps=60.0, cropped_image = [55,610,55,455], rotate_camera = [270],
                 epochs=[100,100], epoch_labels = ["baseline", "occulded"],
                 config_file_path = config_path,
                 reward_size = [45,45],  Prop_Obj_on_Left = [0.5,0.5], 
                 slit_size = [10,2], slit_depth = [2,2], target_spread = [4,4]):
```

Here we have modified the blocks to have 100 trial each by specifying that epochs = [100,100]. We have then named these blocks using epoch_lables = ["baseline", "occuluded"]. Then the only parameter that changes between these two blocks is the size of the slit that the mouse has to look through to see the targets. in the first block this is set to be 10 (the slit is so wide that the objects are unoccluded) where as in the second block the slit size is much lower (slit_size = 2). Under this framework if we call the self.get_epoch_value() the first element in the list is returned if the trial number is less than 100 but if it is more than 100 then the second element in the parameter list is returned. 

Being able to change the parameters in this way allows the user to have control over the task structure and the aesthetics of the game from the GUI








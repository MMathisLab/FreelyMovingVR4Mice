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

In this task a mouse the mouse looks through a slit in the wall and has to report which side an object of interest is on. This object of interest (a green cube) randomly appears on the left or right side of the arena and is occluded by the slit. On the other side a blue cube appears. This document describes how the task is run.


## Python Task
The python [task](https://github.com/MMathisLab/FreelyMovingVR4Mice/blob/mary/demo/mouse_task/mouse_ar_task.py) acts as an interface between DLC and the unity [game](https://github.com/MMathisLab/FreelyMovingVR4Mice/tree/mary/demo/mouse_task/unity_ar) and the teensy. It can be selected from within the teensy experiments GUI by clicking on the "edit" button. Here parameters such as reward size and the probability that the cube will appear on the left can be set. This python script then logs all the data about the experiment such as the mouses position in the arena, when water was given and which side the mouse reported that the target was on.

### Gui Parameters

Here is an explanation of the parameters that can be set in the GUI:

1. reward_size -  This specifies how may ms the water valve should be open for
2. ObI_left -  probability that the object of interest will appear on the left
3. arena_dims - The dimensions of the box that the mouse walking around in  [left, right, top, bottom] all dimensions should be in pixels. These are then mapped to the game space.

such parameters can either be used to control aspects of the game that need to be sent to the teensy such as reward size. Or these parameters can be sent to the unity game on a trial by trial basis to control the unity game parameters.


### Adding new game parameters
New parameters can be added to this task by placing them within the arguments of this class, as done with the "new_param" in the code cell below. These parameters will automatically appear in the GUI when you click on the edit button. 

```{code-cell} ipython3
:tags: [mytag]

def __init__(self, teensy, monitor=None, write_video=False, fps=60.0,
                 epochs=[250],
                 config_file_path = config_path,
                 reward_size = 45, new_param = 0.0):
```

If you want to send these parameters to the teensy you can use the [write function](../teensyexp/teensy.py).
For example see the [check_reward](../mouse_task/mouse_ar_task.py) function, which sends a command to the water pin on the teensy, telling it to open the valve for a set number of ms: 

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


If you want to send these parameters to the unity game this can be done by adding them as a "side channel" in the [set_channel](mouse_task/mouse_ar_task.py) function:

```{code-cell} ipython3
:tags: [set_channel]
def set_channel(self):
        """
            method inherited from task parent class interface
            This function sends parameters to unity when the game is reset - ie at the beginning of each trial
        """

        # extract paramters for the current trial
        this_Prob_obj_left = self.get_epoch_value("Prob_Obj_on_Left")
        this_slit_size = self.get_epoch_value("slit_size")
        this_slit_depth = self.get_epoch_value("slit_depth")


        self.channel.set_property("Prob_Obj_on_Left", this_Prob_obj_left)
        self.channel.set_property("slit_size", this_slit_size)
        self.channel.set_property("slit_depth", this_slit_depth)

        # add trial parameters to trial vectors so that we can save them to the log file
        self.trial_epoch_labels.append(self.get_epoch_value("epoch_labels"))
        self.trial_split_size.append(this_slit_size)
        self.trial_split_depth.append(this_slit_depth)
```

Here the parameter for the current trial is extracted by self.get_epoch_value(). In this example, all 



### The script outline
GUI parameters are taken from the parameters of the class




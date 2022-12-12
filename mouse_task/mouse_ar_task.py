"""
    These module contain Augmented Reality Visual discrimination class,
    used to generate AR task with DLClive position tracking and unity-based visual flow,
    It corresponds to the teensyexp module's protocol, and inherits UnityTask and GuiTask classes,
    that make it possible to be charged via teensyexp gui dynamic module load

    Note: the model path should be defined in the local task_config.json file
"""

from tkinter import Tk, Toplevel, Button
import os
from pathlib import Path
import numpy as np
import time
import pandas as pd
import cv2
import numpy as np
from deeplabcut.utils.auxfun_videos import VideoReader
from tqdm import trange
from dlclive import DLCLive

from mouse_task.helpers import process_config
from mouse_task.dlc_utils.video import Video
from mouse_task.dlc_utils.kfilter import OneEuroFilter
from mouse_task.dlc_utils.dlcProcessor import MyProcessor
from teensyexp.tasks_abc.unity_task import UnityTask
from teensyexp.tasks_abc.gui_task import GuiTask

config_name = Path("task_config.json")
current_dir = Path(__file__).parent
config_path = current_dir.joinpath(config_name) # default class constructor input

class ARVisualDiscrim(UnityTask, GuiTask):
    """
        Augmented Reality Visual discrimination
        Class that represents mouse task, inherits from UnityTask and GuiTask teensyexp module's classes
    """

    def __init__(self, teensy, monitor=None, write_video=False, fps=60.0,
                 epochs=[250],
                 config_file_path = config_path,
                 reward_size = 45):
        """
            Class constructor: initialises dlc processor, dlc live, video reader
            Uses the constructor from parent UnityTask class that creats unity env

            Args:
                teensy(Teensy object): instance of teensy class that controls teensy microcontroller
                monitor: not used
                write_video(boolean): False
                fps: frames per second
                epochs: default 250
                config_file_path(Path object): path to config .json file (more in helpers.py)
                reward size(int):

            Returns:
                instance of ARVisualDiscrim class

        """

        #initialised in init_DLC_live()
        self.t_count = None
        self.filt = None
        self.params = None

        config_dict = process_config(config_file_path)

        if config_dict is None:
        # err messages are showed on process_config() function level
            return

        model_path = config_dict["model_absolute_path"]
        dlc_video_path = config_dict["dlc_video_absolute_path"]
        env_path = config_dict["ar_env_unity_absolute_path"]

        super().__init__(teensy, env_path, monitor=monitor, write_video=write_video, fps=fps, epochs=epochs, epoch_trials=True)

        # reward size
        self.reward_size = reward_size

        # setup video steam and DLC stuff
        self.dlc_proc = MyProcessor()
        self.dlc_live = DLCLive(model_path, processor=self.dlc_proc,display=True, resize =0.6)
        self.video_path = dlc_video_path
        self.vid = VideoReader(video_path=self.video_path)
        self.initialized = False

    def init_dlc_live(self):
        """
            method that initialises the DLC FRAME
            it grabs and filters the current mouse's state
        """

        self.t_count = 0
        _ = self.dlc_live.init_inference(self.vid.read_frame(shrink=1))
        frame = self.vid.read_frame(shrink = 1)
        self.params = self.dlc_live.get_pose(frame)
        self.filt = OneEuroFilter(t0 = self.t_count, x0 = np.array(self.params), beta=0.01, min_cutoff=0.01)
        self.t_count = self.t_count + 1
        x = self.params [0]
        z = self.params [1]
        head_angle = self.params [2]

        # interp mouse pixel space into arena space
        x = np.interp(x,[55,610], [-10,10])
        z = np.interp(z,[55,455], [-4,-15])
        degrees = (head_angle - (90+180)) % 360; 
        output = np.array([x,z,degrees])
        return(output.reshape((1,-1)))

    def _get_dlc_on_frame(self):
        """
            inner method that runS DLC on every frame
            used in get_action(), called by teensyexp's module Agent
        """
        # run DLC on every frame to be given as input to the agent
        frame = self.vid.read_frame(shrink = 1)
        params = self.dlc_live.get_pose(frame)
        self.params =self.filt(self.t_count, np.array(params))
        self.t_count = self.t_count + 1
       
        x = self.params [0]
        z = self.params [1]
        head_angle = self.params [2]

        # interp mouse pixel space into arena space
        x = np.interp(x,[55,610], [-10,10])
        z = np.interp(z,[55,455], [-4,-15])
        degrees = (head_angle - (90+180)) % 360; 
        output = np.array([x,z,degrees])
        return(output.reshape((1,-1)))

        

    # This gui function needs to be here     
    def create_gui(self, parent):
        """
            method inherited from gui_task parent class interface
        """
        pass

    # can use this function to save data to the .pickle file and send parameters to unity
    def set_channel(self):
         """
            method inherited from task parent class interface
        """
         pass

    def get_action(self):
        """
            method that get actions from DLC and parse them to unity
            called by teensyexp's module Agent
        """
        if not self.initialized:
            output = self.init_dlc_live()
            self.initialized = True  
        else:
            output = self._get_dlc_on_frame()
        return output

    def check_reward(self):
        """
            method to set up the reward
        """
        if self.reward > 0:
            print(self.reward_size)
            #self.teensy.write('water', [self.reward_size]) #TODO(tom)

    def reset_environment(self):
        """
            method to reset environment, use parent method implementation call
        """
        super().reset_environment()
        
    def get_info(self):
        """
            method to get information about position and angle on the GUI

            Returns:
                dictionary with 'position' and 'h_angle' keys
        """
        pos = None if self.state is None else "%0.3f, %0.3f" % (self.state[0], self.state[1])
        h_angle = None if self.state is None else "%0.2f" % (self.state[2])

        return {
                'position' : pos,
                'h_angle' : h_angle
            }

        
    def get_data(self):
        """
            method to get data, parent method implementation call

            Returns:
                dictionary with data
        """
        data_dict = super().get_data()
        return data_dict

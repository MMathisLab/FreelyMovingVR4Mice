"""
    These module contain Augmented Reality Visual discrimination class,
    used to generate AR task with DLClive position tracking and unity-based visual flow,
    It corresponds to the teensyexp module's protocol, and inherits UnityTask and GuiTask classes,
    that make it possible to be charged via teensyexp gui dynamic module load

    Note: the model path should be defined in the local task_config.json file
"""

from tkinter import Tk, Toplevel, Button
import os
#os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'
os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "0,1"

from pathlib import Path
import numpy as np
import time
import pandas as pd
import cv2
import numpy as np

from tqdm import trange

import time as time
from multiprocessing.connection import Client

from mouse_task.helpers import process_config

from teensyexp.tasks_abc.unity_task import UnityTask
from teensyexp.tasks_abc.gui_task import GuiTask
from teensyexp.tasks_abc.dlc_socket import DLCClient
from mouse_task.kfilter import OneEuroFilter



config_name = Path("task_config.json")
current_dir = Path(__file__).parent
config_path = current_dir.joinpath(config_name) # default class constructor input

class ARVisualDiscrim_blocks(UnityTask):
    """
        Augmented Reality Visual discrimination
        Class that represents mouse task, inherits from UnityTask and GuiTask teensyexp module's classes
    """

    def __init__(self, teensy, monitor=None, write_video=False, fps=60.0, session_label = ["AR_VD_blocks_training"],
                 epochs=[250], epoch_labels = ["baseline"],
                 config_file_path = config_path,
                 reward_size = 100, cropped_image = [0,530,0,510], unity_arena_size = [-9, 9, -10, -2],
                 R_report_box = [5, 10, -5, -3],
                 L_report_box = [-10, -5, -5, -3], Start_box =  [-4, 4, -9, -5, 90], 
                 rotate_camera = 90, Prop_Obj_on_Left = 1.0, mouse_report_delay = 1,
                 slit_size = 20, slit_depth = 2, target_spread = 8, target_size = 5, target_height = 1, block_length = 20, start_box_delay = 0.25, velocity_threshold=0.8, distractor = 0.0, grey_screen_active = 0.0):

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
        self.address = ('localhost', 6000)
        self.dlcClient = DLCClient(address=self.address)
        self.t_count = 0
        self.degrees = 0
        self.correct = 0
        self.session_label = session_label
        self.grey_screen_active = grey_screen_active
        
        
        config_dict = process_config(config_file_path)

        if config_dict is None:
        # err messages are showed on process_config() function level
            return

        model_path = config_dict["model_absolute_path"]
        dlc_video_path = config_dict["dlc_video_absolute_path"]
        env_path = config_dict["ar_env_unity_absolute_path"]

        super().__init__(teensy, env_path, monitor=monitor, write_video=write_video, fps=fps, epochs=epochs, epoch_trials=True)

        # Game parameters
        self.cropped_image = cropped_image
        self.unity_arena_size = unity_arena_size
        self.rotate_camera = rotate_camera
        self.R_report_box = R_report_box
        self.L_report_box = L_report_box
        self.start_box = Start_box
        self.start_box_delay = start_box_delay
        self.velocity_threshold = velocity_threshold
        
        # Game trial parameters - add to class and enforce list structure
        self.reward_size = self.as_list(reward_size)
        self.slit_size = self.as_list(slit_size)
        self.slit_depth = self.as_list(slit_depth)
        self.epoch_labels = self.as_list(epoch_labels)
        self.target_spread = self.as_list(target_spread)
        self.target_height = self.as_list(target_height)
        self.mouse_report_delay = self.as_list(mouse_report_delay)
        self.Prob_Obj_on_Left = Prop_Obj_on_Left
        self.Prob_L = Prop_Obj_on_Left
        self.Prob_R = 1 - Prop_Obj_on_Left
        self.object_L = 0.0
        self.block_length = block_length
        self.distractor = distractor
        self.target_size = target_size
        

        self.n_rewards = 0

        # create empty vectors to keep track of game parameters per trial
        self.trial_epoch_labels = []
        self.trial_reward_size = []
        self.trial_Prob_Obj_on_Left = []
        self.trial_slit_size = []
        self.trial_slit_depth = []
        self.trial_target_spread = []
        self.trial_target_height = []
        
        self.dlc_x = []
        self.dlc_y = []
        self.dlc_heading = [] 
        self.dlc_time_step = []
        self.trial_mouse_report_delay = []



    def _get_dlc_on_frame(self):
        """
            inner method that runS DLC on every frame
            used in get_action(), called by teensyexp's module Agent
            This is run on every frame after the dlc processor is initialised
        """
        
        # run DLC on every frame to be given as input to the agent
        this_read = self.dlcClient.read()
        #print(this_read)
        if this_read != None:
            self.params = np.array(this_read ["vals"])
            if self.t_count == 0:
                self.filt = OneEuroFilter(t0 = self.t_count, x0 = np.array(self.params), beta=0.01, min_cutoff=0.01)
            else:
                self.params =self.filt(self.t_count, np.array(self.params))
            self.t_count = self.t_count + 1
            x = self.params [0]
            z = self.params [1]
            head_angle = self.params [2]
            self.dlc_x.append(x)
            self.dlc_y.append(z)
            self.dlc_heading.append(head_angle)
            
            # interp mouse pixel space into arena space
            x = np.interp(x,[self.cropped_image[0],self.cropped_image[1]], [self.unity_arena_size [0],self.unity_arena_size [1]])
            z = np.interp(z,[self.cropped_image[2],self.cropped_image[3]], [self.unity_arena_size [2],self.unity_arena_size [3]])
            self.degrees = (head_angle - (self.rotate_camera)) % 360; 
            output = np.array([x,z,self.degrees])
            #print(x, " ", z, " ")
        else:
            output = np.array([0,0,0])
    
     
        return(output.reshape((1,-1)))

        

    # This gui function needs to be here - currently this is not used   
    

    # can use this function to save data to the .pickle file and send parameters to unity
    def set_channel(self):
        """
            method inherited from task parent class interface
            This function sends parameters to unity when the game is reset - ie at the beginning of each trial
        """

        this_Prob_obj_left = self.Prob_Obj_on_Left
        print("prob left", this_Prob_obj_left)
        this_slit_size = self.get_epoch_value("slit_size")
        this_slit_depth = self.get_epoch_value("slit_depth")
        this_target_spread = self.get_epoch_value("target_spread")
        this_target_height = self.get_epoch_value("target_height")
        this_mouse_report_delay = self.get_epoch_value("mouse_report_delay")


        self.channel.set_property("probGreenLeft", this_Prob_obj_left)
        self.channel.set_property("slitSize", this_slit_size)
        self.channel.set_property("slit_depth", this_slit_depth)
        self.channel.set_property("targetsFromMidline", this_target_spread)
        self.channel.set_property("targetsheight", this_target_height)
        self.channel.set_property("mouseReportDelay", this_mouse_report_delay)
        self.channel.set_property("startBoxDelay", self.start_box_delay)
        self.channel.set_property("velocityThreshold", self.velocity_threshold)
        
        # set properties for start box, left report box and right report box
        self.channel.set_property("L_box_x_min", self.L_report_box [0])
        self.channel.set_property("L_box_x_max", self.L_report_box [1])
        self.channel.set_property("L_box_z_min", self.L_report_box [2])
        self.channel.set_property("L_box_z_max", self.L_report_box [3])
        
        self.channel.set_property("R_box_x_min", self.R_report_box [0])
        self.channel.set_property("R_box_x_max", self.R_report_box [1])
        self.channel.set_property("R_box_z_min", self.R_report_box [2])
        self.channel.set_property("R_box_z_max", self.R_report_box [3])
        
        self.channel.set_property("TT_box_x_min", self.start_box [0])
        self.channel.set_property("TT_box_x_max", self.start_box [1])
        self.channel.set_property("TT_box_z_min", self.start_box [2])
        self.channel.set_property("TT_box_z_max", self.start_box [3])
        self.channel.set_property("TT_box_angle", self.start_box [4])
        self.channel.set_property("distractor", self.distractor)
        self.channel.set_property("targetSize", self.target_size)
        self.channel.set_property("Grey_screen_active", self.grey_screen_active)
    
        

        # add trial parameters to trial vectors so that we can save them to the log file
        self.trial_epoch_labels.append(self.get_epoch_value("epoch_labels"))
        self.trial_slit_size.append(this_slit_size)
        self.trial_slit_depth.append(this_slit_depth)
        self.trial_target_spread.append(this_target_spread)
        self.trial_slit_depth.append(this_slit_depth)
        self.trial_target_height.append(this_target_height)
        self.trial_mouse_report_delay.append(this_mouse_report_delay)




    def get_action(self):
        """
            method that get actions from DLC and parse them to unity
            called by teensyexp's module Agent, This function is called on every frame of the game.
        """
        output = self._get_dlc_on_frame()
       
        return output

    def check_reward(self):
        """
            method to set up the reward
        """
        if self.reward > 0:
            self.correct += 1
            
            if self.state [7] > 0:
                print("___ Rewarded - left ___")
                print(self.reward_size)
                self.teensy.write('l_water', [self.reward_size[0]]) 
            else:
                print("___ Rewarded - right ___")
                print(self.reward_size)
                self.teensy.write('r_water', [self.reward_size[0]])
            self.n_rewards += 1
            
            if self.correct == self.block_length:
                if self.object_L == 0.0:
                    self.Prob_Obj_on_Left = self.Prob_L
                    self.object_L = 1.0
                else:
                    self.object_L = 0.0
                    self.Prob_Obj_on_Left = self.Prob_R
                self.correct = 0

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
        velocity = None if self.state is None else "%0.2f" % (self.state[-1])
        in_left_box = None if self.state is None else "%0.2f" % (self.state[7])
        in_right_box = None if self.state is None else "%0.2f" % (self.state[8])
        
        
        

        return {
                'session time' : round(self.cur_time, 1),
                'epoch' : self.epoch_labels[self.epoch],
                'episode' : self.episode,
                'position' : pos,
                'h_angle' : self.degrees,
                'rewards' : self.n_rewards,
                'velocity' : velocity,
                'in_left_box': in_left_box,
                'in_right_box': in_right_box
            }

        
    def get_data(self):
        """
            method to get data, parent method implementation call

            Returns:
                dictionary with data
        """
        data_dict = super().get_data()
        data_dict ["session_label"] = self.session_label
        data_dict['dlc_x'] = np.array(self.dlc_x)
        data_dict['dlc_y'] = np.array(self.dlc_y)
        data_dict['dlc_heading'] = np.array(self.dlc_heading)
        data_dict["block_labels"] = np.array(self.trial_epoch_labels)
        data_dict["slit_size"] = np.array(self.trial_slit_size)
        data_dict["trial_slit_depth"] = np.array(self.trial_slit_depth)
        data_dict["R_report_box"] = np.array(self.R_report_box)
        data_dict["L_report_box"] = np.array(self.L_report_box)
        data_dict["start_box"] = np.array(self.start_box)
        data_dict["cropped_image"] = np.array(self.cropped_image)
        data_dict["unity_arena_size"] = np.array(self.unity_arena_size)
        data_dict["camera_roation"] = np.array(self.rotate_camera)
        data_dict["mouse_report_delay"] = np.array(self.trial_mouse_report_delay)
        data_dict["velocity_threshold"] = self.velocity_threshold
        data_dict["start_box_delay"] = self.start_box_delay
        data_dict ["distractor"] = self.distractor
        data_dict ["target_size"] = self.target_size
        data_dict ["grey_screen_active"] = self.grey_screen_active
        return data_dict

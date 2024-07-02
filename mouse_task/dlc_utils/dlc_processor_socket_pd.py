
import numpy as np


from multiprocessing.connection import Listener
import pickle
import time
from collections import deque
from tests.Teensy_latency.TeensyLatency import TeensyLatency

import numpy as np
from dlclive import Processor
from math import sqrt, acos, atan2, copysign, pi, degrees

class dlc_inference_w_pd(Processor):
    def __init__(self, com = "COM5", baudrate=9600, signal_delay = 10, signal_type ="pulse", freq =5, use_teensy = 1):
        super().__init__()
       # self.queue = queue
        
        self.address = ('localhost', 6000)     # family is deduced to be 'AF_INET'
        self.listener =  Listener(self.address, authkey=b'secret password')
        self.conn = self.listener.accept()
        print('connection accepted from', self.listener.last_accepted)
        
        self.center_x = deque()
        self.center_y = deque()
        self.heading_direction = deque()
        self.head_angle = deque()
        self.time_stamp = deque()
        self.signal =  deque()
        self.step = deque()
        self.frame_time = deque()
        self.pose_time =  deque()
        self.curr_step = 0
        self.curr_signal = 0
        self.start_time = time.time()
        self.signal_type = signal_type
        self.signal_delay =  signal_delay
        self.signal_freq = freq
        if use_teensy == 1:
            self.teensy = TeensyLatency(com, baudrate=baudrate)
            print("using_teensy")
        
    def process(self, pose, **kwargs):
        #print(pose.keys())
        xy = pose[:, :2]
        conf = pose[:, 2]
        head_xy = xy [[0, 1, 2, 3, 4, 5, 6, 26],:]
        head_conf =  conf [[0, 1, 2, 3, 4, 5, 6, 26]]
        center = np.average(head_xy, axis=0, weights=head_conf)
        body_axis = xy[7] - xy[13]  # tail_base -> neck
        body_axis /= sqrt(np.sum(body_axis ** 2))
        head_axis = xy[0] - xy[7]  # neck -> nose
        head_axis /= sqrt(np.sum(head_axis ** 2))
        cross = body_axis[0] * head_axis[1] - head_axis[0] * body_axis[1]
        sign = copysign(1, cross)  # Positive when looking left
        try:
            head_angle = acos(body_axis @ head_axis) * sign
        except ValueError:
            head_angle = 0
            
        self.curr_time = time.time()
        self.curr_signal = self.get_signal(curr_time = self.curr_time, st=self.start_time,
                                           freq = self.signal_freq, 
                                           delay=self.signal_delay,  
                                           signal_type=self.signal_type)
        
        self.curr_step + self.curr_step + 1

        heading = atan2(body_axis[1], body_axis[0])
        heading = degrees(heading)
        vals = *center, heading % (360), head_angle, self.curr_signal
        
        
        self.center_x.append(vals [0])
        self.center_y.append(vals [1])
        #print("center_y: ", vals [1], ", center_x: ", vals [0])
        self.heading_direction.append(vals [2])
        self.head_angle.append(vals [3])
        self.time_stamp.append(self.curr_time)
        self.step.append(self.curr_step)
        self.signal.append(self.curr_signal)
        self.frame_time.append(kwargs ["frame_time"])
       # self.pose_time.append(kwargs ["pose_time"])
        
        self.conn.send([time.time(), vals [0], vals [1], vals [2], vals [3], vals [4]])
     
        return pose
    

    def get_signal(self, signal_type, curr_time, st, freq, delay):
        if signal_type == "pulse":
            curr_signal = self.get_nhz_pulse(curr_time=curr_time, st=st, freq=freq, delay=delay)
        if signal_type == "sin":
            curr_signal = self.get_sin_wave(curr_time=curr_time, st=st, freq=freq, delay=delay)
        if signal_type == "flip":
            curr_signal = self.flip_every_frame(curr_time=curr_time, st=st, delay=delay)
        return(curr_signal)

    
    def get_nhz_pulse(self, curr_time, st, freq, delay):
        if (curr_time - st) < delay:
            curr_signal = 0
        else:
            curr_signal = (np.sign(np.sin(freq*np.pi*time.time()))+1)/2
            #print(curr_signal)
            #self.curr_signal = (np.sin((self.curr_step) * .1) + 1) / 2
        return(curr_signal)      

    def get_sin_wave(self, curr_time, st, delay, freq):
        if (curr_time - st) < delay:
            curr_signal = 0
        else:
            #curr_signal = (np.sign(np.sin(5*np.pi*time.time()))+1)/2
            curr_signal = np.round((np.sin((self.curr_time*freq)) + 1)/ 4,4)
            #print(curr_signal)
        return(curr_signal)
    
    def flip_every_frame(self, curr_time, st, delay):
        if (curr_time - st) < delay:
            curr_signal = 0
        else:
            if self.curr_signal == 0:
                curr_signal = 1
            else:
                curr_signal = 0
        return(curr_signal)
        
    
    def save(self, file=None):
        save_code = 0
        if file:
            print(file)
            try:
                save_dict = self.save_latency_data()
                print(save_dict)
               
                pickle.dump(
                    save_dict,
                    open(file, "wb"),
                )
                save_code = 1
            except Exception:
                save_code = -1
        return save_code
    
    def save_latency_data(self):
        self.teensy.close_serial()
        save_dict =  dict()
        save_dict ["start_time"] = np.array(self.start_time)
        save_dict ["frame_time"] = np.array(self.frame_time)
        #save_dict ["pose_time"] = np.array(self.pose_time)
        save_dict ["time_stamp"] = np.array(self.time_stamp)
        save_dict ["step"] =  np.array(self.step)
        save_dict ["signal"] = np.array(self.signal)
        save_dict ["photodiode_read"] = np.array(self.teensy.input_data)
        save_dict ["photodiode_time"] = np.array(self.teensy.input_data_time)
        save_dict ["x_pos"] =np.array(self.center_x)
        save_dict ["y_pos"] = np.array(self.center_y)
        save_dict ["heading_direction"] = np.array(self.heading_direction)
        save_dict ["head_angle"] = np.array(self.head_angle)
        
        return(save_dict)

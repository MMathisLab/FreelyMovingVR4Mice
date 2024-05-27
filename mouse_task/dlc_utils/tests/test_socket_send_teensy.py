import numpy as np
from multiprocessing.connection import Listener
#from multiprocessing import threading
import threading
import pickle
import time
from teensyexp.teensy import Teensy
import numpy as np
from collections import deque
import serial
from mouse_task.tests.Teensy_latency.TeensyLatency import TeensyLatency

from math import sqrt, acos, atan2, copysign, pi, degrees


class MyProcessor_socket():
    def __init__(self, com = "/dev/tty.usbmodem146851301", baudrate=9600,  save_file_path = "/Users/thomassainsbury/Documents/Mathis_lab/Mathis_lab_code/FreelyMovingVR4Mice/mouse_task/dlc_utils/tests/"):
        super().__init__()
        
        self.address = ("localhost", 6000)  # family is deduced to be 'AF_INET'
        self.listener = Listener(self.address, authkey=b"secret password")
        self.conn = self.listener.accept()
        # add read from config for teensy - to make life simple
        print("connection accepted from", self.listener.last_accepted)
        self.time_stamp = deque()
        self.st = time.time()
        self.curr_step = 0
        self.signal = deque()
        self.step = deque()
        self.teensy = TeensyLatency(com, baudrate=baudrate)
        self.reading_teensy = True


        self.vals = np.array([0.0, -9.0, 0.59740335, 3.0])
        
        self.save_file_path = save_file_path


    def process(self):
        self.vals = self.vals
        self.curr_time = time.time()
        self.get_curr_signal()
        self.conn.send(
            [
                self.curr_time,
                np.sin(self.curr_time*0.5)*9,
                self.vals[1],
                self.vals[2],
                self.vals[3],
                self.curr_signal]
        )
        # self.time_stamp.append(time.time)
        ## Sending data at 50Hz ##
        self.signal.append(self.curr_signal)
        self.step.append(self.curr_step)
        self.time_stamp.append(self.curr_time)
        self.curr_step = self.curr_step + 1
        time.sleep(1 / 50)
        # print(self.st - time.time())

    def get_curr_signal(self):
        if (self.curr_time - self.st) < 3:
            self.curr_signal = 0
        else:
            
            self.curr_signal = (np.sign(np.sin(5*np.pi*time.time()))+1)/2
            #self.curr_signal = (np.sin((self.curr_step) * .1) + 1) / 2
        return(self.curr_signal)
   

    def save(self):
        save_dict =  dict()
        save_dict ["start_time"] = np.array(self.st)
        save_dict ["time_stamp"] = np.array(self.time_stamp)
        save_dict ["step"] =  np.array(self.step)
        save_dict ["signal"] = np.array(self.signal)
        save_dict ["photodiode_read"] = np.array(self.teensy.input_data)
        save_dict ["photodiode_time"] = np.array(self.teensy.input_data_time)
        print(save_dict)
        np.save(arr = save_dict, file=self.save_file_path + "dummy_teensy_dlc", allow_pickle=True)
        print("saved")


socket = MyProcessor_socket()

while True:
    try:
        socket.process()
    except:
        print("exeption")
        socket.teensy.reading_teensy = False
        socket.conn.close()
        socket.save()
        break

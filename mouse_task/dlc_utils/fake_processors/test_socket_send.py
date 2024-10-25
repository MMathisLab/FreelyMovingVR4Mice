import numpy as np
from multiprocessing.connection import Listener
import pickle
import time
from collections import deque
import numpy as np

from math import sqrt, acos, atan2, copysign, pi, degrees


class MyProcessor_socket:
    def __init__(self, save_file_path = "/Users/thomassainsbury/Documents/Mathis_lab/Mathis_lab_code/FreelyMovingVR4Mice/mouse_task/tests/"):
        super().__init__()

        self.address = ("localhost", 6000)  # family is deduced to be 'AF_INET'
        self.listener = Listener(self.address, authkey=b"secret password")
        self.conn = self.listener.accept()
        print("connection accepted from", self.listener.last_accepted)
        self.time_stamp = deque()
        self.st = time.time()
        self.curr_step = 0
        self.signal = deque()
        self.step = deque()
        # self.vals = np.array([0.0, -9.0, 2.0, 3.0])
        self.vals = np.array([0.0, -9.0, 0.59740335, 3.0])
        self.save_file_path = save_file_path

    def process(self):
        self.curr_time = time.time()
        self.get_curr_signal()
        print(self.curr_signal)
        self.conn.send(
            [
                self.curr_time,
                np.sin(self.curr_step*0.1) * 9,
                np.sin(self.curr_step*0.1) * 9,
                self.vals[2],
                self.vals[3],
                self.curr_signal]
        )
        self.signal.append(self.curr_signal)
        self.step.append(self.curr_step)
        self.time_stamp.append(self.curr_time)
        self.curr_step = self.curr_step + 1


        # self.time_stamp.append(time.time)
        ## Sending data at 50Hz ##
        time.sleep(1 / 50)
        # print(self.st - time.time())

    def get_curr_signal(self):
        if (self.curr_time - self.st) < 3:
            print("waiting")
            self.curr_signal = 0
        else:
            self.curr_signal = (np.sin((self.curr_step) * .2) + 1) / 2
        return(self.curr_signal)
    
    def save(self):
        save_dict =  dict()
        save_dict ["start_time"] = np.array(self.st)
        save_dict ["time_stamp"] = np.array(self.step)
        save_dict ["step"] = np.array(self.time_stamp)
        save_dict ["signal"] = np.array(self.signal)
        np.save(arr = save_dict, file=self.save_file_path + "dummy_dlc", allow_pickle=True)
        # np.save(save_dict, )

    

socket = MyProcessor_socket()

while True:
    try:
        socket.process()
    except:
        socket.conn.close()
        socket.save()
        break

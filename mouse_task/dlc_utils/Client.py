import os
import numpy as np

import time
import threading

from multiprocessing.connection import Client
from array import array
import numpy as np
import time

class DLC_client(object):


    def __init__(self, address = ('localhost', 6000)):
        self.address = address
        self.time_step = []
        self.x = []
        self.y = []
        self.reading = True
        self.input_data = []
        self.output_data = []
        self.start_read_buffer()
        while self.reading == True:
            try:
                data = self.read()
                if data != None:
                    print(data)
                    self.time_step.append(data ["time"])
                    self.x.append(data ["vals"][0])
                    self.y.append(data ["vals"][1])
                time.sleep(0.05)
            except:
                break
            

        
        data_dict = {"time": self.time_step, "x": self.x, "y": self.y}
        np.save("/Users/thomassainsbury/Documents/Mathis_lab/socket_test/saved_data/client_tread.npy", data_dict)
        print("client_thread.py saved")

    def read_on_thread(self):
        self.conn = Client(self.address, authkey=b'secret password')
        while self.reading == True: 
            try:
                this_read = self.conn.recv()
                
                self.input_data.append(list((time.time(),this_read)))
            except EOFError:
                self.reading == False
                break

    def start_read_buffer(self):
        self.start_read_time = time.time()
        self.reading = True
        threading.Thread(target=self.read_on_thread, daemon=True).start()

    def read(self, index=-1, input=None):
        if self.input_data != []:
            vals = self.input_data[index]
            return({"time": vals[0], "vals": vals [1]})


DLC_client()
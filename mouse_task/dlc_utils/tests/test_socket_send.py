import numpy as np
from multiprocessing.connection import Listener
import pickle
import time

import numpy as np

from math import sqrt, acos, atan2, copysign, pi, degrees

class MyProcessor_socket():
    def __init__(self):
        super().__init__()
  
        self.address = ('localhost', 6000)     # family is deduced to be 'AF_INET'
        self.listener =  Listener(self.address, authkey=b'secret password')
        self.conn = self.listener.accept()
        print('connection accepted from', self.listener.last_accepted)
        self.time_stamp = []
        self.st = time.time()
        self.vals = np.array([0.,-9.,2.,3.])
        
    def process(self):
        self.vals = self.vals 
        #print(self.vals)
        self.conn.send([time.time(), np.sin(time.time())*9, self.vals [1], self.vals [2], self.vals [3]])
        #self.time_stamp.append(time.time)
        time.sleep(1/20)
        #print(self.st - time.time())

socket = MyProcessor_socket()

while True:
    socket.process()
    

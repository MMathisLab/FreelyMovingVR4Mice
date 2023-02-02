from multiprocessing.connection import Listener
from array import array
import numpy as np

class process():
    def __init__(self):
        self.address = ('localhost', 6000)     # family is deduced to be 'AF_INET'
        self.listener =  Listener(self.address, authkey=b'secret password')
        self.conn = self.listener.accept()
        print('connection accepted from', self.listener.last_accepted)
        while True:
            self.send_array()

    def send_array(self):
        arr = np.random.randint(5, size=10)
        self.conn.send(arr.tolist())

  
process()

import numpy as np
import time
import threading
from multiprocessing.connection import Client
from collections import deque

class DLCClient(object):
    def __init__(self, address=('localhost', 6000)):
        self.address = address
        self.reading = True
        self.input_data = deque() 
        self.save_input_data = deque()
        self.previous =deque() # Using deque for efficient appends
        self.start_read_buffer()
        self.start_time = time.time()

    def read_on_thread(self):
        self.conn = Client(self.address, authkey=b'secret password')
        while self.reading:
            try:
                this_read = self.conn.recv()
                self.input_data.append(this_read)
                
            except EOFError:
                self.reading = False
                break

    def start_read_buffer(self):
        threading.Thread(target=self.read_on_thread, daemon=True).start()

    def read(self):
        if len(self.input_data) >= 1:
            print(len(self.input_data))
            #print(np.diff(np.array(self.input_data)))
            this_read = self.input_data.pop()
            rec_time = time.time()
            self.input_data = deque()
            
            #print(this_read)
            #print("read from incomming:", rec_time, this_read)
            return {"time": rec_time, "vals": this_read, "previous": 0}
        
        #elif self.previous:
        #    rec_time, this_read = self.previous.pop()
        #    rec_time = rec_time
            #print("read from previous", rec_time, this_read, len(self.previous))
         #   return {"time": rec_time, "vals": this_read, "previous": 1}
        
        return None

    def stop(self):
        self.reading = False

    def get_input_data(self):
        return np.array(list(self.input_data))

    def reset(self):
        self.input_data.clear()

    def close(self):
        self.stop()
        self.conn.close()
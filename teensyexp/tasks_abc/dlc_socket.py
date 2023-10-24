import numpy as np
import time
import threading
from multiprocessing.connection import Client
import numpy as np
import time

class DLCClient(object):
    def __init__(self, address = ('localhost', 6000)):
        # start read buffer
        self.address = address
        self.reading = True
        self.input_data = []
        self.start_read_buffer()
       

    def read_on_thread(self):
        # start connection to the socket
        self.conn = Client(self.address, authkey=b'secret password')
        # start reading and add data to a list
        while self.reading == True: 
            try:
                this_read = self.conn.recv()
                self.input_data.append(list((time.time(),this_read)))
            # if the connection on the DLClivegui is closed, stop the thread reading in a clean way
            except EOFError:
                self.reading == False
                break

    def start_read_buffer(self):
        # start reading from DLClivegui in thread
        self.start_read_time = time.time()
        self.reading = True
        threading.Thread(target=self.read_on_thread, daemon=True).start()

    def read(self, index=-1, input=None):
        """
        method to read data that is being writtern by the thread periodically
        """
        if self.input_data != []:
            vals = self.input_data[index]
            return({"time": vals[0], "vals": vals [1]})
    
    def stop(self):

        """
            change the reading class attribute to False (switch flag)
        """
        self.reading = False

    def get_input_data(self, format='array'):
        """
            Attr:
                format: ignored
            returns:
                input_data list as a numpy array
        """
        return np.array(self.input_data)

    def reset(self):
        """
            method reset to empty list input_data and output_data attributes
        """
        self.input_data = []

    def close(self):
        """
            method to stop communication and update reading state attribute to False via stop()
        """
        self.stop()
        self.conn.close()





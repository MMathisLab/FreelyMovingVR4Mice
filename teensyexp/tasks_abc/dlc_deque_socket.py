import numpy as np
import time
import threading
from multiprocessing.connection import Client
from collections import deque


class DLCClient(object):
    def __init__(self, address=("localhost", 6000)):
        self.address = address
        self.reading = True
        self.latest_data = None  
        self.lock = threading.Lock()
        self.conn = Client(self.address, authkey=b"secret password")
        self.start_read_buffer()
        self.start_time = time.time()

    def read_on_thread(self):
        while self.reading:
            try:
                this_read = self.conn.recv()
                self.latest_data = this_read
            except EOFError:
                self.reading = False
                break

    def start_read_buffer(self):
        threading.Thread(target=self.read_on_thread, daemon=True).start()

    def read(self):
        with self.lock:
            if self.latest_data is not None:
                return {"time": time.time(), "vals": self.latest_data}
        return None

    def stop(self):
        self.reading = False

    def close(self):
        self.stop()
        self.conn.close()

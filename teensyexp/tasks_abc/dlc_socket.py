"""Socket-based DLC client using a list-backed read buffer.

Starts a background reader thread that receives DLC frames from DLCLiveGUI
and stores them for task consumption.
"""

import numpy as np
import time
import threading
import socket
from multiprocessing.connection import Connection, answer_challenge, deliver_challenge


class DLCClient(object):
    def __init__(self, address = ('localhost', 6000)):
        # start read buffer
        self.address = address
        self.authkey = b'secret password'
        self.connect_timeout = 0.2
        self._stop_event = threading.Event()
        self.reading = True
        self.input_data = []
        self.start_read_buffer()


    def _connect_with_timeout(self):
        sock = None
        conn = None

        try:
            if isinstance(self.address, tuple):
                sock = socket.create_connection(self.address, timeout=self.connect_timeout)
            else:
                sock = socket.socket(socket.AF_UNIX)
                sock.settimeout(self.connect_timeout)
                sock.connect(self.address)
            sock.settimeout(None)
            conn = Connection(sock.detach())
            answer_challenge(conn, self.authkey)
            deliver_challenge(conn, self.authkey)
            return conn
        except Exception:
            if conn is not None:
                conn.close()
            elif sock is not None:
                sock.close()
            raise

    def read_on_thread(self):
        conn = None
        try:
            # Keep connect attempts bounded so close() can wait synchronously.
            while self.reading and not self._stop_event.is_set():
                try:
                    conn = self._connect_with_timeout()
                    break
                except (TimeoutError, socket.timeout):
                    continue

            if conn is None:
                return

            self.conn = conn
            # start reading and add data to a list
            while self.reading == True:
                try:
                    this_read = conn.recv()
                    self.input_data.append(list((time.time(),this_read)))
                # if the connection on the DLCLiveGUI is closed, or close() ran while
                # recv() was blocked, stop the thread reading in a clean way
                except (EOFError, OSError):
                    self.reading = False
                    break
        finally:
            if conn is not None:
                conn.close()
            self.conn = None

    def start_read_buffer(self):
        # start reading from DLClivegui in thread
        self.start_read_time = time.time()
        self.reading = True
        self._read_thread = threading.Thread(target=self.read_on_thread, daemon=True)
        self._read_thread.start()

    def read(self, index=-1, input=None):
        """
        method to read data that is being writtern by the thread periodically
        """
        if self.input_data != []:
            vals = self.input_data[index]
            return({"time": vals[0], "vals": vals [1]})
    
    def stop(self):
        """Change the reading class attribute to False (switch flag)."""
        self.reading = False
        self._stop_event.set()

    def get_input_data(self, format='array'):
        """
            Attr:
                format: ignored
            returns:
                input_data list as a numpy array
        """
        return np.array(self.input_data)

    def reset(self):
        """Reset input_data to an empty list."""
        self.input_data = []

    def close(self):
        """Stop communication and update reading state attribute."""
        self.stop()
        conn = getattr(self, "conn", None)
        if conn is not None:
            conn.close()
        read_thread = getattr(self, "_read_thread", None)
        if read_thread is not None:
            read_thread.join()








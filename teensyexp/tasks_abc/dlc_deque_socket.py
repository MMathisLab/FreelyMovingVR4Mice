"""Socket-based DLC client using deque-backed buffers.

Starts a background reader thread that receives DLC frames from DLCLiveGUI
and keeps the newest values in deques for low-overhead access.
"""

import numpy as np
import time
import threading
import socket
from multiprocessing.connection import Connection, answer_challenge, deliver_challenge
from collections import deque


class DLCClient(object):
    def __init__(self, address=("localhost", 6000)):
        self.address = address
        self.authkey = b"secret password"
        self.connect_timeout = 0.2
        self._stop_event = threading.Event()
        self.reading = True
        self.input_data = deque()
        self.save_input_data = deque()
        self.previous = deque()  # Using deque for efficient appends
        self.start_read_buffer()
        self.start_time = time.time()

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
            while self.reading:
                try:
                    this_read = conn.recv()
                    self.input_data.append(this_read)

                except (EOFError, OSError):
                    # EOFError: remote side closed cleanly. OSError: local conn.close()
                    # ran while recv() was blocked (e.g. from close()).
                    self.reading = False
                    break
        finally:
            if conn is not None:
                conn.close()
            self.conn = None

    def start_read_buffer(self):
        self._read_thread = threading.Thread(target=self.read_on_thread, daemon=True)
        self._read_thread.start()

    def read(self):
        if len(self.input_data) >= 1:

            this_read = self.input_data.pop()
            rec_time = time.time()
            self.input_data = deque()
            self.previous = this_read

            # print(this_read)
            # print("read from incoming:", rec_time, this_read)
            return {"time": rec_time, "vals": this_read, "previous": 0}

        # elif self.previous:
        #    rec_time, this_read = self.previous.pop()
        #    rec_time = rec_time
        # print("read from previous", rec_time, this_read, len(self.previous))
        #   return {"time": rec_time, "vals": this_read, "previous": 1}

        return None

    def stop(self):
        self.reading = False
        self._stop_event.set()

    def get_input_data(self):
        return np.array(list(self.input_data))

    def reset(self):
        self.input_data.clear()

    def close(self):
        self.stop()
        conn = getattr(self, "conn", None)
        if conn is not None:
            conn.close()
        read_thread = getattr(self, "_read_thread", None)
        if read_thread is not None:
            read_thread.join()

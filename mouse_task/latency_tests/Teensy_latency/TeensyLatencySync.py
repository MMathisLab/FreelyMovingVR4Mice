import numpy as np
import threading 
import time
import serial
from collections import deque
import logging

logging.basicConfig(level=logging.INFO)

class TeensyLatency():
    def __init__(self, com, baudrate):
        self.com = com
        self.baudrate = baudrate
        self.logger = logging.getLogger("TeensyLatency")
        self.input_data = deque()
        self.input_data_time = deque()
        self.input_data_teensy_time = deque()
        self.input_data_ttl = deque()
        self.reading_teensy = True
        self.stop_event = threading.Event()
        self.start_read_buffer()


    def read_on_thread(self):
        while not self.stop_event.is_set():
            line = self.ser.readline().decode("utf-8").rstrip()
            now = time.time()  # Current time
            input_parts = line.split(',')
            try:
                self.input_data.append(input_parts[0])
                self.input_data_time.append(now)
                self.input_data_ttl.append(input_parts[1] if len(input_parts) > 1 else None)
                self.input_data_teensy_time.append(input_parts[2] if len(input_parts) > 2 else None)
            except Exception as e:
                self.logger.error(f"Error processing line: {line}. Error: {e}", exc_info=True)

    def start_read_buffer(self):
        """
            method that starts the reader thread (reader for serial buffer), writer for (input_data)
            saves the time of start
        """
        self.ser = serial.Serial(self.com, self.baudrate)
        self.start_read_time = time.time()
        self.reading = False #True
        threading.Thread(target=self.read_on_thread, daemon=True).start()
        self.logger.debug(f"Started reading from Teensy on {self.com} at {self.baudrate} baud.")

    def _stop_reading(self):
        """
        method to stop reading from teensy
        """
        self.stop_event.set()
     
    def close_serial(self):
        self._stop_reading()  # Signal the thread to stop
        self.ser.close()
        self.logger.debug(f"Stopped reading and closed serial connection on {self.com}.")
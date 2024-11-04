import numpy as np
import threading
import time
import serial


class TeensyLatency:
    def __init__(self, com, baudrate):
        self.com = com
        self.baudrate = baudrate
        self.input_data = []
        self.input_data_time = []
        self.reading_teensy = True
        self.start_read_buffer()

    def read_on_thread(self):
        while self.reading_teensy == True:
            try:
                line = self.ser.readline().decode("utf-8").rstrip()
                now = time.time()  # Current time
                self.input_data.append(float(line))
                self.input_data_time.append(now)
            except:
                self.close_serial()
                self.reading = False

    def start_read_buffer(self):
        """
        method that starts the reader thread (reader for serial buffer), writer for (input_data)
        saves the time of start
        """
        self.ser = serial.Serial(self.com, self.baudrate)
        self.start_read_time = time.time()
        self.reading = False  # True
        threading.Thread(target=self.read_on_thread, daemon=True).start()

    def close_serial(self):
        self.ser.close()

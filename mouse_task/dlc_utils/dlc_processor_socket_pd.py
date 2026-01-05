import pickle
import time
import warnings
from collections import deque
from math import acos, atan2, copysign, degrees, pi, sqrt
from multiprocessing.connection import Listener

import numpy as np

from latency_tests.Teensy_latency.TeensyLatency import TeensyLatency
from mouse_task.dlc_utils.dlc_processor_socket import MyProcessor_socket


class dlc_inference_w_pd(MyProcessor_socket):
    def __init__(
        self,
        com="COM3",
        baudrate=9600,
        signal_delay=10,
        signal_type="pulse_geo",
        freq=5,
        use_teensy=1,
    ):
        super().__init__(signal_delay=signal_delay, signal_type=signal_type, freq=freq)

        self.use_teensy = use_teensy
        self.previous = np.array([0, 0])
        if self.use_teensy == 1:
            self.teensy = TeensyLatency(com, baudrate=baudrate)
            print("Using Teensy")

    def save_latency_data(self):
        if self.use_teensy == 1:
            print("Closing serial connection to teensy")
            self.teensy.close_serial()

        save_dict = dict()
        save_dict["start_time"] = np.array(self.start_time)
        save_dict["frame_time"] = np.array(self.frame_time)
        save_dict["time_stamp"] = np.array(self.time_stamp)
        save_dict["step"] = np.array(self.step)
        save_dict["signal"] = np.array(self.signal)

        if self.use_teensy == 1:
            save_dict["photodiode_read"] = np.array(self.teensy.input_data)
            save_dict["photodiode_time"] = np.array(self.teensy.input_data_time)

        save_dict["x_pos"] = np.array(self.center_x)
        save_dict["y_pos"] = np.array(self.center_y)
        save_dict["heading_direction"] = np.array(self.heading_direction)
        save_dict["head_angle"] = np.array(self.head_angle)
        return save_dict

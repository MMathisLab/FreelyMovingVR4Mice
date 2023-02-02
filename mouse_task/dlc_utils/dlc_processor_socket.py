import cv2
import numpy as np
#from .Video_handler import VideoReader
from tqdm import trange
from dlclive import DLCLive
from multiprocessing.connection import Listener

import numpy as np
from dlclive import Processor
from math import sqrt, acos, atan2, copysign, pi, degrees

class MyProcessor_socket(Processor):
    def __init__(self, baudrate=115200, pulse_freq=50, pulse_width=5, max_stim_dur=0):
        super().__init__()
        self.address = ('localhost', 6000)     # family is deduced to be 'AF_INET'
        self.listener =  Listener(self.address, authkey=b'secret password')
        self.conn = self.listener.accept()
        print('connection accepted from', self.listener.last_accepted)
       # self.queue = queue

    def process(self, pose, **kwargs):
        xy = pose[:, :2]
        conf = pose[:, 2]
        center = np.average(xy, axis=0, weights=conf)
        body_axis = xy[7] - xy[13]  # tail_base -> neck
        body_axis /= sqrt(np.sum(body_axis ** 2))
        head_axis = xy[0] - xy[7]  # neck -> nose
        head_axis /= sqrt(np.sum(head_axis ** 2))
        cross = body_axis[0] * head_axis[1] - head_axis[0] * body_axis[1]
        sign = copysign(1, cross)  # Positive when looking left
        head_angle = acos(body_axis @ head_axis) * sign
        heading = atan2(body_axis[1], body_axis[0])
        heading = degrees(heading)
        vals = *center, heading % (360), head_angle
        self.conn.send([center [0], center [1]])
       # if self.queue is not None:
       #     self.queue.write(vals)
        #print(vals)
        return pose
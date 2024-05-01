
import numpy as np


from multiprocessing.connection import Listener
import pickle
import time
from collections import deque

import numpy as np
from dlclive import Processor
from math import sqrt, acos, atan2, copysign, pi, degrees

class MyProcessor_socket(Processor):
    def __init__(self):
        super().__init__()
       # self.queue = queue
        self.address = ('localhost', 6000)     # family is deduced to be 'AF_INET'
        self.listener =  Listener(self.address, authkey=b'secret password')
        self.conn = self.listener.accept()
        print('connection accepted from', self.listener.last_accepted)
        self.center_x =[]
        self.center_y = []
        self.heading_direction = []
        self.head_angle = []
        self.time_stamp = []
        
    def process(self, pose, **kwargs):
        xy = pose[:, :2]
        conf = pose[:, 2]
        head_xy = xy [[0, 1, 2, 3, 4, 5, 6, 26],:]
        head_conf =  conf [[0, 1, 2, 3, 4, 5, 6, 26]]
        center = np.average(head_xy, axis=0, weights=head_conf)
        body_axis = xy[7] - xy[13]  # tail_base -> neck
        body_axis /= sqrt(np.sum(body_axis ** 2))
        head_axis = xy[0] - xy[7]  # neck -> nose
        head_axis /= sqrt(np.sum(head_axis ** 2))
        cross = body_axis[0] * head_axis[1] - head_axis[0] * body_axis[1]
        sign = copysign(1, cross)  # Positive when looking left
        try:
            head_angle = acos(body_axis @ head_axis) * sign
        except ValueError:
            head_angle = 0
        heading = atan2(body_axis[1], body_axis[0])
        heading = degrees(heading)
        vals = *center, heading % (360), head_angle
        
        self.center_x.append(vals [0])
        self.center_y.append(vals [1])
        self.heading_direction.append(vals [2])
        self.head_angle.append(vals [3])
        self.time_stamp.append(time.time())
        
        self.conn.send([vals [0], vals [1], vals [2], vals [3]])
     
        return pose
    
    def save(self, file=None):

        ### save stim on and stim off times
        save_code = 0
        if file:
            try:
                pickle.dump(
                    {"time_stamp": self.time_stamp, "x_pos": self.center_x, "y_pos": self.center_y, "heading_direction": self.heading_direction, "head_angle": self.head_angle},
                    open(file, "wb"),
                )
                save_code = 1
            except Exception:
                save_code = -1
        return save_code
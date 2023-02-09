import cv2
import numpy as np
#from .Video_handler import VideoReader
from tqdm import trange
from dlclive import DLCLive

import numpy as np
from dlclive import Processor
from math import sqrt, acos, atan2, copysign, pi, degrees

class MyProcessor(Processor):
    def __init__(self, queue=None):
        self.queue = queue

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
        try:
            head_angle = acos(body_axis @ head_axis) * sign
        except ValueError:
            head_angle = 0
        heading = atan2(body_axis[1], body_axis[0])
        heading = degrees(heading)
        vals = *center, heading % (360), head_angle
        if self.queue is not None:
            self.queue.write(vals)
        #print(vals)
        return pose, vals
    
        def save(self, filename):

        ### save stim on and stim off times

        if filename[-4:] != ".npy":
            filename += ".npy"
        arr = np.array(self.led_times, dtype=float)
        try:
            np.save(filename, arr)
            save_code = True
        except Exception:
            save_code = False

        return save_code

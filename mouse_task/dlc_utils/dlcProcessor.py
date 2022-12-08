import cv2
import numpy as np
from deeplabcut.utils.auxfun_videos import VideoReader
from tqdm import trange
from dlclive import DLCLive

import numpy as np
from dlclive import Processor
from math import sqrt, acos, atan2, copysign, pi, degrees

class MyProcessor(Processor):

    def process(self, pose):
        
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
        return(*center, heading % (360), head_angle)



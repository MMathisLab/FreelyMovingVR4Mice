import numpy as np
from dlclive.processor.processor import Processor
from math import sqrt, acos, atan2, copysign, degrees
import pickle

class dlc_only(Processor):
    def __init__(self,  con = 50, com=2):
        super().__init__()
        self.x = []

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
        head_angle = acos(body_axis @ head_axis) * sign
        heading = atan2(body_axis[1], body_axis[0])
        heading = degrees(heading)
        vals = *center, heading % (360), head_angle
        self.x.append(center)
        return pose
    
    def save(self, filename):

        ### save stim on and stim off times
    
        filename += ".npy"
        try:
            np.savez(
                filename, out_time=self.x)
            save_code = True
        except Exception:
            print("not saved")
            save_code = False

        return save_code
        
    
    
   
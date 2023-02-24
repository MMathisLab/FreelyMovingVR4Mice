import numpy as np
from dlclive.processor.processor import Processor
from math import sqrt, acos, atan2, copysign, degrees

class MyProcessor2(Processor):
    def __init__(self,  con = 50):
        super().__init__()
   

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
        head_angle = acos(body_axis @ head_axis) * sign
        heading = atan2(body_axis[1], body_axis[0])
        heading = degrees(heading)
        vals = *center, heading % (360), head_angle
        print(vals)
       # if self.queue is not None:
       #     self.queue.write(vals)
        return pose
    
    def save(self, file=None):

        ### save stim on and stim off times
        save_code = 0
        return save_code
    
    
   
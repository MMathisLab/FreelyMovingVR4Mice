import numpy as np
from dlclive import Processor
from math import sqrt, acos, atan2, copysign, pi, degrees

class MyProcessor(Processor):
    def __init__(self, var = 0):
        super().__init__()
        self.var = var
        pass

    def process(self, pose, **kwargs):
        print(pose[0, 2])
        return pose
    
    def save(self, filename):
        pass

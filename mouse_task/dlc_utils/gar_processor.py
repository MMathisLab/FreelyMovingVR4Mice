"""
DeepLabCut Toolbox (deeplabcut.org)
© A. & M. Mathis Labs
Licensed under GNU Lesser General Public License v3.0
"""


from dlclive.processor.processor import Processor

import struct
import pickle
import time


class TeensyLaser(Processor):
    def __init__(
        self, com, baudrate=115200, pulse_freq=50, pulse_width=5, max_stim_dur=0
    ):

        super().__init__()
       # self.ser = serial.Serial(com, baudrate)
  

    
     

    def process(self, pose, **kwargs):

        # define criteria to stimulate (e.g. if first point is in a corner of the video)
        

        return pose


from dlclive.processor.processor import Processor
import serial
import struct
import pickle
import time


class TeensyLaser(Processor):
    def __init__(
        self, com = 50, conn=2):

        super().__init__()
        self.stim_on_time = []
      

    def process(self, pose, **kwargs):

        # define criteria to stimulate (e.g. if first point is in a corner of the video)
        self.stim_on_time.append(time.time())
        

        return pose

    def save(self, file=None):

        ### save stim on and stim off times
        save_code = 0
        if file:
            try:
                pickle.dump(
                    {"stim_on": self.stim_on_time},
                    open(file, "wb"),
                )
                save_code = 1
            except Exception:
                save_code = -1
        return save_code
from dlclive.processor.processor import Processor
import pickle
import time
from dlclivegui.processors import PROCESSOR_REGISTRY, register_processor  # type: ignore[import-not-found]

PROCESSOR_REGISTRY.pop("TeensyLaser", None)


@register_processor
class TeensyLaser(Processor):
    PROCESSOR_NAME = "TeensyLaser"
    PROCESSOR_DESCRIPTION = "Simple processor that logs stimulation timestamps."
    PROCESSOR_PARAMS = {
        "com": {
            "type": "int",
            "default": 50,
            "description": "Reserved COM parameter (currently unused).",
        },
        "conn": {
            "type": "int",
            "default": 2,
            "description": "Reserved connection parameter (currently unused).",
        },
    }

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


def get_available_processors():
    return {
        "TeensyLaser": {
            "class": TeensyLaser,
            "name": getattr(TeensyLaser, "PROCESSOR_NAME", "TeensyLaser"),
            "description": getattr(TeensyLaser, "PROCESSOR_DESCRIPTION", ""),
            "params": getattr(TeensyLaser, "PROCESSOR_PARAMS", {}),
        }
    }

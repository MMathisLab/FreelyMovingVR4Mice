import sys
import importlib as imp
import time
import numpy as np
from pathlib import Path

from mouse_task.mouse_detection_p1 import Detection_p1
from teensyexp.agent import Agent

# from mlagents_envs.environment import ActionTuple
# from mlagents_envs.environment import UnityEnvironment
# from mlagents_envs.side_channel.environment_parameters_channel import (
#     EnvironmentParametersChannel,
# )

config_name = Path("task_config.json")
current_dir = Path(__file__).parent
config_path = current_dir.joinpath(config_name)

agent = Agent()
arVDtask = Detection_p1(
    agent
)

start_time = time.time()

#arVDtask.channel.set_float_parameter("occlusion_type", 0.0)
arVDtask.start()
arVDtask.env.reset()

while time.time() - start_time < 10:
    arVDtask.loop()

print(f"properties dict: {arVDtask.occlusion_type}")

arVDtask.stop()

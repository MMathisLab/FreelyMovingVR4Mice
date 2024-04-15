import sys
import importlib as imp
import time
import numpy as np

from mouse_task.mouse_VisualDiscrim_single_teardrop_blocks import (
    ARVisualDiscrim_single_teardrop,
)
from teensyexp.agent import Agent

# from mlagents_envs.environment import ActionTuple
# from mlagents_envs.environment import UnityEnvironment
# from mlagents_envs.side_channel.environment_parameters_channel import (
#     EnvironmentParametersChannel,
# )

agent = Agent()
arVDtask = ARVisualDiscrim_single_teardrop(
    agent, occlusion_type=1.0, slit_size=2.0, slit_depth=0.1
)

start_time = time.time()

# arVDtask.channel.set_float_parameter("occlusion_type", 1.0)
arVDtask.start()

while time.time() - start_time < 10:
    arVDtask.loop()

print(f"properties dict: {arVDtask.channel_dict}")
print(f"slit_size: {arVDtask.get_epoch_value('slit_size')}")
print(f"occlusion_type: {arVDtask.get_epoch_value('occlusion_type')}")
arVDtask.stop()

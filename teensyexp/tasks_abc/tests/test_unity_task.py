import sys
import time
import numpy as np

from teensyexp.tasks_abc.unity_task import UnityTask
from mlagents_envs.environment import ActionTuple
from mlagents_envs.environment import UnityEnvironment
from mlagents_envs.side_channel.environment_parameters_channel import (
    EnvironmentParametersChannel,
)

from teensyexp.agent import Agent

env_path = "/Users/subnaulitus/Documents/EPFL/GitHub_Repos/FreelyMovingVR4Mice/mouse_task/macOS_test_unity_build/vr4mice.app"
agent = Agent()
task = UnityTask(
    teensy=agent,
    env=env_path,
)

# task.start()
# task.channel.set_float_parameter("occlusion_type", 1.0)
# task.channel.set_property("slitSize", 20.0)
start_time = time.time()

# print(f"properties: {task.channel.list_properties()}")
task.start()

# task.channel.set_property("slitSize", 100.0)
# print(f"properties: {task.channel.list_properties()}")
# task.reset_environment()

while time.time() - start_time < 10:
    task.loop()
    # print(task.get_state())

# print(f"slitSize: {task.get_epoch_value('slitSize')}")
# print("data: ", task.get_data())
task.stop()

# channel = EnvironmentParametersChannel()
# # channel = EnvironmentParametersChannel()
# env = UnityEnvironment(file_name=env_path, side_channels=[channel])

# env.reset()
# behavior_name = list(env.behavior_specs)[0]
# print(f"Name of the behavior : {behavior_name}")
# spec = env.behavior_specs[behavior_name]

# if spec.action_spec.continuous_size > 0:
#     print(f"There are {spec.action_spec.continuous_size} continuous actions")

# steps = env.get_steps(behavior_name)
# print(f"Steps: {steps[0].get('AgentPosition')}")

# start_time = time.time()
# while time.time() - start_time < 10:
#     random_action = np.array(
#         [np.sin(time.time()) * 9, -9.0, 0.59740335], dtype=np.float32
#     ).reshape(1, -1)
#     # # print(random_action)
#     action_tuple = ActionTuple()
#     action_tuple.add_continuous(random_action)
#     env.set_actions(behavior_name, action_tuple)
#     env.step()

# # time.sleep(5)
# env.close()

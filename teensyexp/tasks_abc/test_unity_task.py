import sys
import time

from unity_task import UnityTask

sys.path.append("..")
from agent import Agent

env_path = "/Users/subnaulitus/Documents/EPFL/GitHub_Repos/FreelyMovingVR4Mice/mouse_task/macOS_test_unity_build/vr4mice.app"
agent = Agent()
task = UnityTask(
    teensy=agent,
    env=env_path,
)

task.start()
# print("step result: ", task.get_step_result())
# print("reward: ", task.get_step_result().reward)
# print("state: ", task.get_state())

start_time = time.time()

while time.time() - start_time < 10:
    task.loop()

task.stop()

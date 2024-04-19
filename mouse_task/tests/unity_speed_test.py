import matplotlib.pyplot as plt
import numpy as np
import time
from collections import deque
from teensyexp.tasks_abc.dlc_deque_socket import DLCClient
from mlagents_envs.environment import UnityEnvironment
from mlagents_envs.environment import ActionTuple, BaseEnv
from mlagents_envs.side_channel.engine_configuration_channel import (
    EngineConfigurationChannel,
)
from mlagents_envs.side_channel.environment_parameters_channel import (
    EnvironmentParametersChannel,
)

# Define the path to the Unity environment binary
# env_name = "/Users/thomassainsbury/Documents/Mathis_lab/Mathis_lab_code/FreelyMovingVR4Mice/mouse_task/mac_build/game.app"
env_name = "/Users/subnaulitus/Documents/EPFL/GitHub_Repos/FreelyMovingVR4Mice/mouse_task/macOS_test_unity_build/vr4mice.app"
train_mode = True  # Whether to run the environment in training or inference mode

# Initialize DLCClient and Unity environment
channel = EnvironmentParametersChannel()
# channel = EnvironmentParametersChannel()
env = UnityEnvironment(file_name=env_name, side_channels=[channel])

# channel.set_configuration_parameters(time_scale = 1)
# channel.set_configuration_parameters(capture_frame_rate=50)

# Reset the environment
# Reset the environment
print("Resetting game...")
env.reset()
behavior_name = list(env.behavior_specs)[0]
print(f"Name of the behavior : {behavior_name}")
spec = env.behavior_specs[behavior_name]

if spec.action_spec.continuous_size > 0:
    print(f"There are {spec.action_spec.continuous_size} continuous actions")
if spec.action_spec.is_discrete():
    print(f"There are {spec.action_spec.discrete_size} discrete actions")

if spec.action_spec.discrete_size > 0:
    for action, branch_size in enumerate(spec.action_spec.discrete_branches):
        print(f"Action number {action} has {branch_size} different options")

# Run the environment for a fixed amount of time
start_time = time.time()
sent_times = deque()
read_times = deque()
data = deque()
loop_end_time = deque()


decision_steps, terminal_steps = env.get_steps(behavior_name)
tracked_agent = -1  # -1 indicates not yet tracking
done = False  # For the tracked_agent
episode_rewards = 0

address = ("localhost", 6000)
dlcClient = DLCClient(address=address)


while (time.time() - start_time) < 10:
    this_read = dlcClient.read()
    # if this_read is None:
    # 	 print(this_read)
    if this_read is not None:
        # if this_read ["time"] - this_read ["vals"][0] < 0.01:
        print(f"sent data: {this_read['vals'][1]}")
        sent_times.append(this_read["vals"][0])
        read_times.append(this_read["time"])
        data.append(this_read["vals"][1])
        # Track the first agent we see if not tracking
        # Note : len(decision_steps) = [number of agents that requested a decision]
        if tracked_agent == -1 and len(decision_steps) >= 1:
            tracked_agent = decision_steps.agent_id[0]
        # Generate an action for all agents
        # action = spec.action_spec.random_action(len(decision_steps))
        # print(action.continuous)

        # Set the actions
        random_action = np.array(
            [
                this_read["vals"][1],
                this_read["vals"][2],
                0.59740335,
                this_read["vals"][-1],
            ],
            dtype=np.float32,
        ).reshape(1, -1)
        print(random_action)
        action_tuple = ActionTuple()
        action_tuple.add_continuous(random_action)
        env.set_actions(behavior_name, action_tuple)

        # Move the simulation forward
        env.step()

        # time.sleep(1/50)

        # Get the new simulation results
        decision_steps, terminal_steps = env.get_steps(behavior_name)
        if tracked_agent in decision_steps:  # The agent requested a decision
            episode_rewards += decision_steps[tracked_agent].reward
        if tracked_agent in terminal_steps:  # The agent terminated its episode
            episode_rewards += terminal_steps[tracked_agent].reward
            done = True
        end_time = time.time()
        loop_end_time.append(end_time)
        print(end_time - this_read["time"])
        # if  (1-(end_time -this_read ["time"])) < 1:
        #    time.sleep(0.9 - (end_time - this_read ["time"]))

    # print(f"Total rewards for episode {episode} is {episode_rewards}")

env.close()
# Sleep briefly to control loop rate (adjust as needed)


time_diff = np.array(read_times) - np.array(sent_times)
filt_sent_times = np.array(sent_times) - start_time
filt_read_times = np.array(read_times) - start_time
filt_loop_end_time = np.array(loop_end_time) - start_time

data = np.array(data)

# Compute and print latency and rate statistics
valid_times = filt_sent_times > 3
mean_latency = np.mean(time_diff[valid_times]) * 1000
mean_rate = np.mean(np.diff(filt_sent_times[valid_times])) * 1000

print("latency:", mean_latency)
print("rate:", mean_rate)

# Plot latency scatter and histogram
plt.figure()
plt.scatter(filt_sent_times[valid_times], time_diff[valid_times] * 1000)
plt.xlabel("Time (s)")
plt.ylabel("Latency (ms)")
plt.title("Latency Scatter Plot")
plt.show()

plt.figure()
plt.hist(time_diff[valid_times] * 1000, bins=50, range=(0, 50))
plt.xlabel("Latency (ms)")
plt.ylabel("Frequency")
plt.title("Latency Histogram")
plt.show()

# Plot data over time
plt.figure()
plt.scatter(filt_sent_times[valid_times], data[valid_times])
plt.scatter(filt_read_times[valid_times], data[valid_times])
plt.scatter(filt_loop_end_time[valid_times], data[valid_times])
plt.xlabel("Time (s)")
plt.ylabel("Data")
plt.xlim(5.4, 6.2)
plt.title("Data over Time")
plt.show()


plt.figure()
plt.scatter(
    filt_sent_times[valid_times],
    (filt_loop_end_time[valid_times] - filt_sent_times[valid_times]) * 1000,
)
plt.xlabel("Time (s)")
plt.ylabel("Delta time")
plt.title("sent to end of unity loop")
plt.show()

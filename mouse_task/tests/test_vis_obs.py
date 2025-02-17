import time as t
from mlagents_envs.environment import UnityEnvironment, ActionTuple
from mlagents_envs.side_channel.environment_parameters_channel import (
    EnvironmentParametersChannel,
)
from test_helpers import dict_to_data_frame, DebugLogSideChannel
from tkinter import filedialog

import tkinter as tk
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

try:
    env.close()
except:
    pass

# Create channels
rl_channel = EnvironmentParametersChannel()
debug_channel = DebugLogSideChannel()

# Pass the parameter 'rl_training'
rl_channel.set_float_parameter("rl_training", 0.0)

# Whether to use the Unity editor or the Build
unity_editor = False

if unity_editor:
    # Will wait for Unity editor to connect
    env = UnityEnvironment(
        base_port=5004,
        side_channels=[rl_channel, debug_channel],
    )
else:
    # Dynamically load the game executable (depens on user's choice)
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(title="Select game executable")
    root.destroy()

    # Load custom unity executable
    env = UnityEnvironment(
        file_name=file_path,
        base_port=5004,
        additional_args=["-monitor", "0", "-fullscreen", "0"],
        side_channels=[rl_channel, debug_channel],
    )

# Reset the environment (needs to happen shortly after initialization for environment parameters to be set)
env.reset()

# Only considering the first Behavior
behavior_name = list(env.behavior_specs)[0]
print(f"Name of the behavior : {behavior_name}")
spec = env.behavior_specs[behavior_name]

# Examining the number of observations per Agent
print("Number of observations : ", len(spec.observation_specs))

# Is there a visual observation ?
# Visual observation have 3 dimensions: Height, Width and number of channels
vis_obs = any(len(spec.shape) == 3 for spec in spec.observation_specs)
print("Is there a visual observation ?", vis_obs)

# Is the Action continuous or multi-discrete ?
if spec.action_spec.continuous_size > 0:
    print(f"There are {spec.action_spec.continuous_size} continuous actions")
if spec.action_spec.is_discrete():
    print(f"There are {spec.action_spec.discrete_size} discrete actions")

# For discrete actions only : How many different options does each action has ?
if spec.action_spec.discrete_size > 0:
    for action, branch_size in enumerate(spec.action_spec.discrete_branches):
        print(f"Action number {action} has {branch_size} different options")

decision_steps, terminal_steps = env.get_steps(behavior_name)
env.set_actions(behavior_name, spec.action_spec.empty_action(len(decision_steps)))
env.step()

for index, obs_spec in enumerate(spec.observation_specs):
    if len(obs_spec.shape) == 3:
        print("Here is the first visual observation")
        plt.imshow(np.moveaxis(decision_steps.obs[index][0, :, :, :], 0, -1))
        plt.show()

for index, obs_spec in enumerate(spec.observation_specs):
    if len(obs_spec.shape) == 1:
        print("First vector observations : ", decision_steps.obs[index][0, :])

trajectories_df = dict_to_data_frame(pd.read_pickle("./data_original.pkl"))
by_ep = trajectories_df.set_index(["step"])

step = 1
for episode in trajectories_df.episode.unique():
    env.reset()
    decision_steps, terminal_steps = env.get_steps(behavior_name)
    tracked_agent = -1  # -1 indicates not yet tracking
    episode_rewards = 0  # For the tracked_agent
    done = False

    episode_actions = trajectories_df

    while not done and step <= trajectories_df.step.max():
        # Track the first agent we see if not tracking
        # Note : len(decision_steps) = [number of agents that requested a decision]
        if tracked_agent == -1 and len(decision_steps) >= 1:
            tracked_agent = decision_steps.agent_id[0]

        # Generate an action for all agents
        print(f"{episode}, {step}")
        action = np.array(
            by_ep.loc[step][
                ["action_x", "action_y", "action_head_angle", "action_photodiode"]
            ].tolist()
        ).reshape((1, -1))

        action_tuple = ActionTuple()
        action_tuple.add_continuous(action)

        # Set the actions
        env.set_actions(behavior_name, action_tuple)

        # Move the simulation forward
        env.step()
        step += 1

        if not (step % 100):
            for index, obs_spec in enumerate(spec.observation_specs):
                if len(obs_spec.shape) == 3:
                    plt.imshow(
                        np.moveaxis(decision_steps.obs[index][0, :, :, :], 0, -1)
                    )
                    plt.savefig(f"./vis_obs/{step}_visual_observation.png")

        # Get the new simulation results
        decision_steps, terminal_steps = env.get_steps(behavior_name)
        if tracked_agent in decision_steps:  # The agent requested a decision
            episode_rewards += decision_steps[tracked_agent].reward
        if tracked_agent in terminal_steps:  # The agent terminated its episode
            print("terminated episode")
            episode_rewards += terminal_steps[tracked_agent].reward
            done = True
        # t.sleep(1 / 50)

    print(f"Total rewards for episode {episode} is {episode_rewards}")

# Close the environment
env.close()
print("Closed environment")

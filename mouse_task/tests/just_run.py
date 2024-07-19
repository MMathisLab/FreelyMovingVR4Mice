from mlagents_envs.environment import UnityEnvironment
from mlagents_envs.side_channel.engine_configuration_channel import (
    EngineConfigurationChannel,
)
import time
import numpy as np
from mlagents_envs.environment import ActionTuple, BaseEnv
from mouse_task.helpers import process_config
from pathlib import Path

# Define your environment path
# env_name = "/Users/thomassainsbury/Documents/Mathis_lab/Mathis_lab_code//roller_ball/roller_ball.app"
# env_name = "/Users/thomassainsbury/Documents/Mathis_lab/Mathis_lab_code/FreelyMovingVR4Mice/mouse_task/mac_build/game.app"
env_name = process_config(Path("../task_config.json"))["ar_env_unity_absolute_path"]

# Initialize the Unity environment
env = UnityEnvironment(file_name=env_name, seed=1, side_channels=[])
channel = EngineConfigurationChannel()
channel.set_configuration_parameters(time_scale=1)
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

# Define your action space (this will depend on your specific environment)
# Example: Assuming a discrete action space with 3 possible actions
num_actions = 3

# Run the simulation for a specified number of steps
for episode in range(3):
    env.reset()
    decision_steps, terminal_steps = env.get_steps(behavior_name)
    tracked_agent = -1  # -1 indicates not yet tracking
    done = False  # For the tracked_agent
    episode_rewards = 0  # For the tracked_agent
    while not done:
        # env.reset()
        # Track the first agent we see if not tracking
        # Note : len(decision_steps) = [number of agents that requested a decision]
        if tracked_agent == -1 and len(decision_steps) >= 1:
            tracked_agent = decision_steps.agent_id[0]
            print("made it")

        # Generate an action for all agents
        action = spec.action_spec.random_action(
            len(decision_steps)
        )  # (len(decision_steps))
        print(action.continuous)
        random_action = np.array(
            [-0.04102117, -9.93074882, 0.59740335], dtype=np.float32
        ).reshape(1, -1)
        print(random_action)
        action_tuple = ActionTuple()
        action_tuple.add_continuous(random_action)
        env.set_actions(behavior_name, action_tuple)

        # Set the actions
        # env.set_actions(behavior_name, action)

        # Move the simulation forward
        env.step()
        time.sleep()

        # Get the new simulation results
        decision_steps, terminal_steps = env.get_steps(behavior_name)
        if tracked_agent in decision_steps:  # The agent requested a decision
            episode_rewards += decision_steps[tracked_agent].reward
        if tracked_agent in terminal_steps:  # The agent terminated its episode
            episode_rewards += terminal_steps[tracked_agent].reward
            done = True
        # time.sleep(0.01)
    print(f"Total rewards for episode {episode} is {episode_rewards}")

# Close the environment
env.close()

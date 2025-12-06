from mlagents_envs.environment import UnityEnvironment
from mlagents_envs.side_channel.engine_configuration_channel import (
    EngineConfigurationChannel,
)
import time
import numpy as np
from mlagents_envs.environment import ActionTuple, BaseEnv
from mouse_task.tests.Teensy_latency.TeensyLatency import TeensyLatency
from collections import deque
from mouse_task.helpers import process_config
import json

# Define your environment path
config_file_path = "../task_config.json"
with open(config_file_path) as task_config_file:
    config_dict = json.load(task_config_file)
env_name = config_dict["ar_env_unity_absolute_path"]


class SendRandomActions:
    def __init__(
        self,
        env_name=config_dict,
        use_teensy=False,
        sleep_time=0,
        loop_time=20,
        signal_delay_time=3,
        signal_type="pulse_geo",
        com="COM3",
        baudrate=9600,
    ):
        self.env = UnityEnvironment(file_name=env_name, seed=1, side_channels=[])
        self.channel = EngineConfigurationChannel()
        self.use_teensy = use_teensy
        self.channel.set_configuration_parameters(time_scale=1)
        # Reset the environment
        print("Resetting game...")
        self.env.reset()
        self.behavior_name = list(self.env.behavior_specs)[0]
        print(f"Name of the behavior : {self.behavior_name}")
        self.spec = self.env.behavior_specs[self.behavior_name]

        if self.spec.action_spec.continuous_size > 0:
            print(
                f"There are {self.spec.action_spec.continuous_size} continuous actions"
            )
        if self.spec.action_spec.is_discrete():
            print(f"There are {self.spec.action_spec.discrete_size} discrete actions")

        if self.spec.action_spec.discrete_size > 0:
            for action, branch_size in enumerate(
                self.spec.action_spec.discrete_branches
            ):
                print(f"Action number {action} has {branch_size} different options")

        # Define your action space (this will depend on your specific environment)
        # Example: Assuming a discrete action space with 3 possible actions
        self.num_actions = 4
        self.st = time.time()
        self.curr_signal = 0

        # Run the simulation for a specified number of steps
        self.env.reset()
        self.decision_steps, self.terminal_steps = self.env.get_steps(
            self.behavior_name
        )
        self.tracked_agent = -1  # -1 indicates not yet tracking
        self.done = False  # For the tracked_agent
        self.episode_rewards = 0  # For the tracked_agent
        self.signal_delay_time = signal_delay_time
        self.signal_type = signal_type
        if use_teensy is True:
            self.teensy = TeensyLatency(com, baudrate=baudrate)
            print("using_teensy")

        self.time_stamp = deque()
        self.st = time.time()
        self.curr_step = 0
        self.signal = deque()
        self.step = deque()
        self.reading_teensy = True
        self.loop(loop_time=loop_time, sleep_time=sleep_time)

    def get_nhz_pulse(self, curr_time, st, freq):
        if (curr_time - st) < self.signal_delay_time:
            self.curr_signal = 0
        else:
            self.curr_signal = (np.sign(np.sin(freq * np.pi * time.time())) + 1) / 2
        return self.curr_signal

    def get_sin_wave(self, curr_time, st):
        if (curr_time - st) < self.signal_delay_time:
            curr_signal = 0
        else:
            curr_signal = np.round((np.sin((curr_time * 5)) + 1) / 4, 4)
            print(curr_signal)
        return curr_signal

    def flip_every_frame(self, curr_time, st):
        if (curr_time - st) < self.signal_delay_time:
            curr_signal = 0
        else:
            if self.curr_signal == 0:
                curr_signal = 1
            else:
                curr_signal = 0
        return curr_signal

    def get_nhz_pulse_jittered(
        self,
        curr_time: float,
        st: float,
        freq: float,
        delay: float,
        max_extra: float = 0.5,
        base_unit: float = 0.005,
    ) -> float:
        if (curr_time - st) < delay:
            return 0

        # Flip state and reschedule when toggle time is reached
        if curr_time >= self.next_jitter_toggle:
            # Flip TTL state
            self.curr_signal = 1 - self.curr_signal

            # Calculate next toggle time with jitter
            half_period = 0.5 / max(freq, 1e-6)
            p = min(0.999, max(1e-6, base_unit * max(freq, 1e-6)))
            extra = np.random.geometric(p) * base_unit  # jitter duration (s)
            extra = min(extra, max_extra)  # cap long tails
            self.next_jitter_toggle = curr_time + half_period + extra

        return self.curr_signal

    def loop(self, loop_time=20, sleep_time=0):
        while (time.time() - self.st) < loop_time:
            # Track the first agent we see if not tracking
            # Note : len(decision_steps) = [number of agents that requested a decision]
            if self.tracked_agent == -1 and len(self.decision_steps) >= 1:
                self.tracked_agent = self.decision_steps.agent_id[0]

            # Generate an action for all agents
            self.action = self.spec.action_spec.random_action(len(self.decision_steps))
            curr_time = time.time()
            if self.signal_type == "pulse":
                self.curr_signal = self.get_nhz_pulse(
                    curr_time=curr_time, st=self.st, freq=5
                )
            if self.signal_type == "sin":
                self.curr_signal = self.get_sin_wave(curr_time=curr_time, st=self.st)
            if self.signal_type == "flip":
                self.curr_signal = self.flip_every_frame(
                    curr_time=curr_time, st=self.st
                )
            if self.signal_type == "pulse_geo":
                self.curr_signal = self.get_nhz_pulse_jittered(
                    curr_time=curr_time,
                    st=self.st,
                    freq=5,
                    delay=self.signal_delay_time,
                )
            random_action = np.array(
                [np.sin(curr_time * 0.5) * 9, -9.0, 0.0, self.curr_signal],
                dtype=np.float16,
            ).reshape(1, -1)

            action_tuple = ActionTuple()
            action_tuple.add_continuous(random_action)
            self.env.set_actions(self.behavior_name, action_tuple)
            self.signal.append(self.curr_signal)
            self.step.append(self.curr_step)
            self.time_stamp.append(curr_time)

            # Move the simulation forward
            self.env.step()
            time.sleep(sleep_time)

            # Get the new simulation results
            self.decision_steps, self.terminal_steps = self.env.get_steps(
                self.behavior_name
            )
            if (
                self.tracked_agent in self.decision_steps
            ):  # The agent requested a decision
                self.episode_rewards += self.decision_steps[self.tracked_agent].reward
            if (
                self.tracked_agent in self.terminal_steps
            ):  # The agent terminated its episode
                self.episode_rewards += self.terminal_steps[self.tracked_agent].reward
                done = True
        self.env.close()

    def save_data(self):
        save_dict = dict()
        save_dict["start_time"] = np.array(self.st)
        save_dict["time_stamp"] = np.array(self.time_stamp)
        save_dict["step"] = np.array(self.step)
        save_dict["signal"] = np.array(self.signal)
        if self.use_teensy is True:
            if len(self.teensy.input_data) != len(self.teensy.input_data_time):
                input_time = np.array(self.teensy.input_data_time[:-1])
            else:
                input_time = np.array(self.teensy.input_data_time)
            save_dict["photodiode_read"] = np.array(self.teensy.input_data)
            save_dict["photodiode_time"] = np.array(input_time)

        np.save(
            arr=save_dict, file="random_actions_" + self.signal_type, allow_pickle=True
        )


# Close the environment
if __name__ == "__main__":
    game = SendRandomActions(
        env_name=env_name,
        signal_type="sin",
        use_teensy=True,
        loop_time=60,
        sleep_time=0.02,
    )
    game.save_data()

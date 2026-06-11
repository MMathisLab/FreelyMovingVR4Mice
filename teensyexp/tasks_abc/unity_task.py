"""
Contains the definition of UnityTask class that should be used for video-game based tasks
for which the game is designed using the [Unity ML-Agents Platform]
"""

import os
import sys
import time
import numpy as np
from mlagents_envs.environment import ActionTuple
from mlagents_envs.environment import UnityEnvironment
from mlagents_envs.side_channel.float_properties_channel import FloatPropertiesChannel
from mlagents_envs.side_channel.environment_parameters_channel import (
    EnvironmentParametersChannel,
)
import cv2
from teensyexp.tasks_abc.task import Task


class UnityTask(Task):
    """
    Unity Task class
    """

    def __init__(
        self,
        teensy,
        env,
        agent_group=0,
        monitor=1,
        fullscreen=1,
        write_video=False,
        fps=60.0,
        epochs=[1e5],
        epoch_trials=True,
    ):
        """
        Args:
            teensy(Teensy object): instance of teensy class
            env(str): the path to the Unity game executable
            agent_group(int): indicator of the group of the agent to be controlled, should almost always be left as the default (0)
            monitor(int): the monitor on which to display the game
            fullscreen(int): should the monitor be displayed in fullscreen mode (1) or as a window (0)
            write_video(boolean): should a video of visual observations be written. Caution: if possible, games should not include visual observations, as this really slows down the speed of the game.
            fps(float): the frame rate at which to write the video of visual observations
            epochs: how many trials (or how long) before parameter should be changed. The task will end at the end of the last epoch is the game trial based (1) or time based (0)
            epoch_trials(boolean): is the game trial based (1) or time based (0)

            call of parent's class constructor

        """
        super().__init__(teensy)

        self.env_path = env
        self.display_args = ["-monitor", str(monitor), "-fullscreen", str(fullscreen)]
        self.agent_group = agent_group
        self.agent_num = 0
        self.channel = EnvironmentParametersChannel()

        self.epochs = np.cumsum(self.as_list(epochs))
        self.epoch_trials = epoch_trials
        self.epoch = 0
        self.episode = 0
        self.step = 0
        self.ep_reward = 0
        self.terminal = False
        self.cur_time = 0
        self.episode_start_time = 0

        self.episode_vec = []
        self.step_vec = []
        self.time_vec = []
        self.state_vec = []
        self.action_vec = []
        self.reward_vec = []
        self.terminal_vec = []
        self.channel_dict = {}

    def start(self):
        """Start unity game.
        
        Initializes UnityEnvironment, extracts agents, set up state observations,
        use parent's start() call to notify teensy
        """
        # Start Unity game
        self.set_channel()

        self.env = UnityEnvironment(
            file_name=self.env_path,
            base_port=5004,
            additional_args=self.display_args,
            side_channels=[self.channel],
        )

        self.env.reset()
        self.agent = list(self.env.behavior_specs)[0]
        self.agent_spec = self.env.behavior_specs[self.agent]

        # Set up state observations and video (if necessary)
        obs_shapes = [obs_spec.shape for obs_spec in self.agent_spec.observation_specs]
        obs_dim = [len(shape) for shape in obs_shapes]
        self.vec_obs_ind = np.where(np.array(obs_dim) == 1)[0][0]
        self.vis_obs_inds = np.where(np.array(obs_dim) == 3)[0]
        vis_obs_ind = self.vis_obs_inds[0] if len(self.vis_obs_inds) > 0 else None
        if vis_obs_ind is not None:
            vis_obs_shape = obs_shapes[vis_obs_ind]
            # Uncomment the following line and define create_vid_writer if video writing is needed
            # self.vid_writer = sefl.create_vid_writer(vis_obs_shape, fps) if write_video else None

        # Access the environment state
        decision_steps, terminal_steps = self.env.get_steps(self.agent)
        self.state = decision_steps.obs[self.vec_obs_ind]
        self.episode = 1

        # Start Teensy
        super().start()

    def as_list(self, val):
        """
        helpers: cast to list
        """
        return val if type(val) is list else [val]

    def get_epoch_value(self, name):
        """Get the epoch
        
        Args:
            name(str): name of the attribute to extract
        
        Returns:
            value of attribute that corresponds to the epoch or last one known

        """
        vals = getattr(self, name)
        return vals[min(self.epoch, len(vals) - 1)]

    def create_vid_writer(self, im_shape, fps):
        """
        method to record the mice visual perception [currently not used]
        output in '/Documents/teensyexp/tmp'
        """
        home_folder = (
            os.environ["USERPROFILE"] if "win" in sys.platform else os.environ["HOME"]
        )
        tmp_dir = os.path.normpath(home_folder + "/Documents/teensyexp/tmp")
        if not os.path.isdir(tmp_dir):
            os.mkdir(tmp_dir)

        tmp_file = os.path.normpath(tmp_dir + "/unity_video.avi")
        im_shape = self.obs_dim[self.obs_dim == 3]
        return cv2.VideoWriter(
            tmp_file, cv2.VideoWriter_fourcc(*"DIVX"), fps, (im_shape[1], im_shape[0])
        )

    def get_step_result(self):
        """Get the step from env agent.
        
        Returns:
            step (DecisionSteps or TerminalSteps)
        """
        # Retrieve DecisionSteps and TerminalSteps for the specified agent group
        decision_steps, terminal_steps = self.env.get_steps(self.agent)

        # Check if the agent is done (terminated)
        if self.agent_num in terminal_steps.agent_id:
            # Return TerminalSteps which contains the last observation, reward, etc., for the agent
            step_result = terminal_steps[self.agent_num]
            self.done = True
        else:
            # Return DecisionSteps which contains the current observation, reward, etc., for the agent
            step_result = decision_steps[self.agent_num]
            self.done = False

        return step_result

    def get_state(self):
        """
        getters for state
        """
        #NOTE(leo): could it be just self.get_step_result().obs?
        return self.get_step_result().obs[self.vec_obs_ind]

    def set_channel(self):
        """
        inherited from parent class interface
        """
        pass

    def log_channel(self):
        """
        method to associate proprieties from channel to channel_dict
        """
        props = self.channel.list_properties()

        if len(self.channel_dict) == 0:
            for prop in props:
                self.channel_dict[prop] = []

        for prop in props:
            self.channel_dict[prop].append(self.channel.get_property(prop))

    def get_action(self):
        """
        Getter for actions
        """
        # Determine action type and create a zero array of the appropriate type
        if self.agent_spec.action_spec.is_continuous():
            dtype = np.float32
            action_size = self.agent_spec.action_spec.continuous_size
            action = np.array(
                [
                    np.sin(time.time()) * 9,
                    -9.0,
                    0.59740335,
                    (np.sin(time.time() * 4) + 1) / 2,
                ],
                dtype=dtype,
            )

        if self.agent_spec.action_spec.is_discrete():
            dtype = np.int32
            action_size = self.agent_spec.action_spec.discrete_size
            action = np.zeros(len(action_size), dtype=dtype)

        return action

    def check_reward(self):
        """
        Inherited from parent class interface
        """
        pass

    def reset_environment(self):
        """
        method to reset environment
        increments agent's number
        """
        self.set_channel()
        self.env.reset()
        # step_result = self.get_step_result()
        # self.state = step_result.obs[self.vec_obs_ind]
        self.ep_reward = 0
        self.episode_start_time = self.cur_time

    def loop(self):
        """
        method that holds the task logic: corresponds to the task execution, supports the data exchange with unity
        updates all the attributes every frame
        """
        self.step += 1

        self.cur_time = time.time() - self.start_time

        self.episode_vec.append(self.episode)  # trial
        self.step_vec.append(self.step)  # frame
        self.time_vec.append(self.cur_time)  # time for each frame

        # Get action
        self.action = self.get_action()  # mouse's moves
        self.action_vec.append(self.action)

        # Take step in environment
        action_tuple = ActionTuple()
        action_tuple.add_continuous(self.action.reshape(1, -1))
        self.env.set_actions(self.agent, action_tuple)

        self.env.step()  # unity env++

        # Get observations
        step_result = self.get_step_result()
        if hasattr(self, "vid_writer"):
            self.vid_writer.write(step_result.obs[self.vis_obs_ind])

        self.reward = step_result.reward
        self.reward_vec.append(self.reward)
        self.ep_reward += self.reward

        self.terminal = self.done  # last frame --> next trial
        self.terminal_vec.append(self.terminal)
        self.check_reward()

        # Get information about the agent
        self.state = step_result.obs[self.vec_obs_ind]
        info = self.get_info()

        self.state_vec.append(self.state)  # all info about the agent (ex. position)

        # Check reset, epochs, and condition to end session; update state
        if self.terminal:
            self.episode += 1
            if (self.epoch_trials) & (self.episode > self.epochs[self.epoch]):
                self.epoch += 1
                if self.epoch > len(self.epochs) - 1:
                    return False, info
            self.reset_environment()
            self.terminal = False

        if (not self.epoch_trials) & (
            self.cur_time - self.start_time > self.epochs[self.epoch]
        ):
            self.epoch += 1
            if self.epoch > len(self.epochs) - 1:
                return False, info

        return True, info

    def get_info(self):
        """
        Returns:
            dictionary containing the information about session time, episode, episode_time
        """
        return {
            "session time": round(self.cur_time - self.start_time, 1),
            "episode": self.episode,
            "episode_time": round(self.cur_time - self.episode_start_time, 1),
        }

    def get_data(self):
        """
        Returns:
            dictionary containing the numpy arrays
        """
        data_dict = {
            "start_time": self.start_time,
            "episode": np.array(self.episode_vec),
            "step": np.array(self.step_vec),
            "step_time": np.array(self.time_vec),
            "state": np.vstack(np.array(self.state_vec, dtype=object)),
            "action": np.array(self.action_vec),
            "reward": np.array(self.reward_vec),
            "terminal": np.array(self.terminal_vec),
        }

        data_dict.update(self.channel_dict)
        return data_dict

    def stop(self):
        """Stop the task

        Send stop message to teensy via parent's call and close the unity env
        """
        super().stop()
        self.env.close()

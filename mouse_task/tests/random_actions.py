from mlagents_envs.environment import UnityEnvironment
from mlagents_envs.side_channel.engine_configuration_channel import EngineConfigurationChannel
import time
import numpy as np
from mlagents_envs.environment import ActionTuple, BaseEnv

# Define your environment path
#env_name = "/Users/thomassainsbury/Documents/Mathis_lab/Mathis_lab_code//roller_ball/roller_ball.app"
env_name = "/Users/thomassainsbury/Documents/Mathis_lab/Mathis_lab_code/FreelyMovingVR4Mice/mouse_task/mac_build/game.app"

class send_random_actions():
  def __init__(self, env_name = env_name, use_teensy = False, sleep_time =0, loop_time=20, signal_delay_time =3, signal_type="sin"):
    self.env = UnityEnvironment(file_name=env_name, seed=1, side_channels=[])
    self.channel = EngineConfigurationChannel()
    self.channel.set_configuration_parameters(time_scale = -1)
    # Reset the environment
    print("Resetting game...")
    self.env.reset()
    self.behavior_name = list(self.env.behavior_specs)[0]
    print(f"Name of the behavior : {self.behavior_name}")
    self.spec = self.env.behavior_specs[self.behavior_name]

    if self.spec.action_spec.continuous_size > 0:
        print(f"There are {self.spec.action_spec.continuous_size} continuous actions")
    if self.spec.action_spec.is_discrete():
        print(f"There are {self.spec.action_spec.discrete_size} discrete actions")

    if self.spec.action_spec.discrete_size > 0:
        for action, branch_size in enumerate(self.spec.action_spec.discrete_branches):
            print(f"Action number {action} has {branch_size} different options")

    # Define your action space (this will depend on your specific environment)
    # Example: Assuming a discrete action space with 3 possible actions
    self.num_actions = 4
    self.st = time.time()
    self.curr_signal = 0

    # Run the simulation for a specified number of steps

    self.env.reset()
    self.decision_steps, self.terminal_steps = self.env.get_steps(self.behavior_name)
    self.tracked_agent = -1 # -1 indicates not yet tracking
    self.done = False # For the tracked_agent
    self.episode_rewards = 0 # For the tracked_agent
    self.signal_delay_time = signal_delay_time
    self.signal_type = signal_type
    self.loop(loop_time=20, sleep_time=sleep_time)


  def get_nhz_pulse(self, curr_time, st, freq):
    if (curr_time - st) < self.signal_delay_time:
        self.curr_signal = 0
    else:
        self.curr_signal = (np.sign(np.sin(freq*np.pi*time.time()))+1)/2
        #self.curr_signal = (np.sin((self.curr_step) * .1) + 1) / 2
    return(self.curr_signal)      

  def get_sin_wave(self, curr_time, st):
    if (curr_time - st) < self.signal_delay_time:
        curr_signal = 0
    else:
        #curr_signal = (np.sign(np.sin(5*np.pi*time.time()))+1)/2
        curr_signal = np.round((np.sin((self.curr_time*5)) + 1)/ 2,4)
        print(curr_signal)
    return(curr_signal)
  
  def flip_every_frame(self, curr_time, st):
    if (curr_time - st) < self.signal_delay_time:
        curr_signal = 0
    else:
        if self.curr_signal == 0:
           curr_signal = 1
        else:
           curr_signal = 0
    return(curr_signal)
      
       


  def loop(self, loop_time = 20, sleep_time = 0):
      while (time.time() - self.st) < loop_time:
      #env.reset()
        # Track the first agent we see if not tracking
      # Note : len(decision_steps) = [number of agents that requested a decision]
          if self.tracked_agent == -1 and len(self.decision_steps) >= 1:
            self.tracked_agent = self.decision_steps.agent_id[0]

          # Generate an action for all agents
          self.action = self.spec.action_spec.random_action(len(self.decision_steps)) 
          #print(action.continuous)
          self.curr_time = time.time()
          if self.signal_type == "pulse":
            self.curr_signal = self.get_nhz_pulse(curr_time=self.curr_time, st=self.st, freq=5)
          if self.signal_type == "sin":
             self.curr_signal = self.get_sin_wave(curr_time=self.curr_time, st=self.st)
          if self.signal_type == "flip":
             self.curr_signal = self.flip_every_frame(curr_time=self.curr_time, st=self.st)

          random_action = np.array([np.sin(self.curr_time*0.5)*9, -9.0,  0.0,  self.curr_signal], dtype=np.float16).reshape(1,-1)
          print(random_action)
          action_tuple = ActionTuple()
          action_tuple.add_continuous(random_action)
          self.env.set_actions(self.behavior_name, action_tuple)
        
          # Move the simulation forward
          self.env.step()
          time.sleep(sleep_time)
          
          # Get the new simulation results
          self.decision_steps, self.terminal_steps = self.env.get_steps(self.behavior_name)
          if self.tracked_agent in self.decision_steps: # The agent requested a decision
            self.episode_rewards += self.decision_steps[self.tracked_agent].reward
          if self.tracked_agent in self.terminal_steps: # The agent terminated its episode
            self.episode_rewards += self.terminal_steps[self.tracked_agent].reward
            done = True
      self.env.close()
      
      
    

# Close the environment
game = send_random_actions(env_name = env_name, signal_type="flip", sleep_time = 0.1)


    









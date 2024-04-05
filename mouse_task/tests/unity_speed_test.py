env_name = "/Users/thomassainsbury/Documents/Mathis_lab/Mathis_lab_code/FreelyMovingVR4Mice/mouse_task/mac_build/game.app"  # Name of the Unity environment binary to launch
train_mode = True  # Whether to run the environment in training or inference mode

import matplotlib.pyplot as plt
import numpy as np
import sys
import time
from teensyexp.tasks_abc.dlc_deque_socket import DLCClient
from collections import deque
from mlagents_envs.environment import UnityEnvironment
from mlagents_envs.side_channel.engine_configuration_channel import EngineConfig, EngineConfigurationChannel


print("Python version:")
print(sys.version)

# check Python version
if (sys.version_info[0] < 3):
    raise Exception("ERROR: ML-Agents Toolkit (v0.3 onwards) requires Python 3")

engine_configuration_channel = EngineConfigurationChannel()
env = UnityEnvironment(base_port = 5004, file_name=env_name, side_channels = [engine_configuration_channel])
address = ('localhost', 6000)
dlcClient = DLCClient(address=address)
#Reset the environment
env.reset()
sent_times = deque()
read_times = deque()
data =  deque()

# Set the default brain to work with
group_name = env.get_agent_groups()[0]
group_spec = env.get_agent_group_spec(group_name)

# Set the time scale of the engine
engine_configuration_channel.set_configuration_parameters(time_scale = 1.0)
start_time = time.time()

env.reset()

while (time.time() - start_time) < 10:
    
    step_result = env.get_step_result(group_name)
    done = False
    episode_rewards = 0
    this_read = dlcClient.read()
    current_time = time.time()
    if this_read is None: 
        print(this_read)
        pass
   #elif (current_time - this_read ["vals"][0]) > 0.01:
    #    pass
    else:
        sent_times.append(this_read ["vals"][0])
        read_times.append(current_time)
        
        action_size = group_spec.action_size
        
            #action = np.random.randn(step_result.n_agents(), group_spec.action_size)
        action = np.array(this_read ["vals"] [2:]).reshape((1,-1))
            #print("TRue")
            
        #if group_spec.is_action_discrete():
        #    branch_size = group_spec.discrete_action_branches
        #    action = np.column_stack([np.random.randint(0, branch_size[i], size=(step_result.n_agents())) for i in range(len(branch_size))])
        env.set_actions(group_name, action)
        
        env.step()
        step_result = env.get_step_result(group_name)
        data.append(step_result.obs[0][0][-1])
        episode_rewards += step_result.reward[0]
        
        
time_diff =  np.array(read_times) - np.array(sent_times) 
times = np.array(sent_times) - start_time
data = np.array(data)
print("latency:", np.mean(time_diff [times > 3])*1000)
print("rate: ", np.mean(np.diff(times [times > 3]))*1000)

plt.scatter(times [times > 3], time_diff [times > 3]*1000)
plt.ylabel("ms")
plt.show()

plt.hist(time_diff [times > 3]*1000, bins=50)
plt.xlim(0,50)
plt.xlabel("ms")
plt.title("rate")
plt.show()

print(data)

plt.plot(times [times > 3], data [times > 3])

plt.show()
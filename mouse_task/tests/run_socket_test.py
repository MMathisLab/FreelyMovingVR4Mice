from mouse_test_socket_speed import ARVisualdiscrim_socket_test
import pickle
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import time

save_path = "/Volumes/Elements/Documents/Mathis_lab/Aug_Reg/"

Task = ARVisualdiscrim_socket_test()

# Now task has all the functions that a MouseTrack_RLsim class has, that inherits from Unity Tasks
# Meaning that from here, you can start the game and loop through the loop function
# Which handles the frames/time in the environement!
Task.start()
Task.env.reset()

while (time.time() - Task.start_time) < 60:
    Task.loop()
    #Task.env.step()
    #print(Task.state [-1])

data = Task.get_data()

print(len(data ["thread_read_time"]) == len(data["step_time"]))



a = pd.DataFrame({"socket_send_time": data ["socket_send_time"] - data["start_time"],
                "thread_read_time": data ["thread_read_time"]- data["start_time"], 
                "step_time": data["step_time"], "diode_state": np.array(Task.state_vec) [:,-1], 
                "episode": data ["episode"], "step": data ["step"], "vals": np.array(Task.state_vec) [:,0]})
a = a [a.socket_send_time > 3]
a ["time_across_socket"] = a["thread_read_time"] - a["socket_send_time"]

plt.scatter(a.socket_send_time, a.time_across_socket*1000)
plt.ylabel("ms")
plt.title("Socket_transfer_speed")
plt.show()




a ["full_latency"] = a["step_time"] -  a["socket_send_time"]
print("Full latency (ms): ", np.mean(a.full_latency)*1000)
plt.scatter(a.socket_send_time, a.full_latency*1000)
plt.ylabel("ms")
plt.title("latency (DLC to unity)")
plt.show()


plt.scatter(a["step_time"], np.gradient(a["step_time"])*1000)
plt.title("rate")
plt.ylabel("ms")
plt.show()


plt.plot(a["step_time"], a ["diode_state"])
plt.show()

plt.scatter(a["step_time"], a ["vals"])
#plt.scatter(a["step_time"], a ["step"])
plt.show()
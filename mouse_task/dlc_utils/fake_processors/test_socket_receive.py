from teensyexp.tasks_abc.dlc_deque_socket import DLCClient
import time
import numpy as np
from collections import deque
import pickle
import os


address = ("localhost", 6000)
dlcClient = DLCClient(address=address)
time_from_send = deque()
time_from_rec = deque()
vals = deque()
previous_used = deque()
start_time = time.time()


def save_data(path="latency_tests_results/received.pickle"):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    data_dict = dict()
    data_dict["send_time"] = np.array(time_from_send)
    data_dict["recieve_time"] = np.array(time_from_rec)
    data_dict["previous_used"] = np.array(previous_used)

    with open(path, "wb") as f:
        pickle.dump(data_dict, f)


while True:
    this_read = dlcClient.read()
    if this_read != None:
        print(this_read)
        time_from_send.append(this_read["time"])
        time_from_rec.append(time.time())
        previous_used.append(this_read["previous"])
        vals.append(this_read["vals"][0])
        time.sleep(1 / 50)
    if (time.time() - start_time) > 100:
        save_data()
        break

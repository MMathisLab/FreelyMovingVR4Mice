from teensyexp.tasks_abc.dlc_deque_socket import DLCClient
import time
import numpy as np
from collections import deque
import pickle



address = ('localhost', 6000)
dlcClient = DLCClient(address=address)
time_from_send = deque()
time_from_rec = deque()
vals = deque()
previous_used = deque()
start_time = time.time()

def save_data(path="/Users/thomassainsbury/Documents/Mathis_lab/socket_test_2/recieved.pickle"):
    #print(dlcClient.input_save_data)
    
    print()
    data_dict = dict()
    data_dict ["send_time"] = np.array(time_from_send)
    data_dict ["recieve_time"] = np.array(time_from_rec)
    data_dict ["previous_used"] = np.array(previous_used)
    #data_dict ["true_send_time"] =  np.array(dlcClient.input_data)[:,0]
    #data_dict ["true_recieve_time"] = np.array(dlcClient.input_data)[:,1]
    
    pickle.dump(data_dict, open(path, 'wb'))
   

while True:
    this_read = dlcClient.read()
    if (this_read != None):
        print(this_read)
        time_from_send.append(this_read ["time"])
        time_from_rec.append(time.time())
        previous_used.append(this_read ["previous"])
        vals.append(this_read ["vals"][0])
        #print(time_from_send[-1] - time_from_rec[-1])
        time.sleep(1/50)
    if (time.time() - start_time) > 100:
        save_data()
        break
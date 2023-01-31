'''
File contains Base task class that should be implemented by all tasks to use with teensyexp

GK 05/07/2019
'''

import time
import numpy as np

class Task:
    """
        general class task (can be seen as abstract class even if no ABC)
        parent class of all tasks
    """
    def __init__(self, teensy):
        """
            class constructor:
                contains teensy object (by ref)
                reset teensy after attaching
            Args:
                teensy(Teensy object): instance of teensy class
            Note: part of attributed are defined locally in methods
            Note: callback for Gui's "Ready"
        """
        self.teensy = teensy
        self.teensy.reset()

        self.states = []
        self.state = None
        self.state_entries = []
        self.state_session = []

        self.cur_time = 0

    def start(self):
        """
            method to start the task, send to teensy "start" message, pause for synchronisation
            update state variables
            tracks the start time
            callback function: `start` is called when the `Start` button on GUI clicked
        """
        self.teensy.write('start')
        self.task_on = True
        time.sleep(.01)
        self.start_time = time.time()

    def move_to_state(self, state):
        """
            method to log states per session and timeslots
        """
        state_num = np.where(np.array(self.states) == state)[0][0]
        self.state = state_num
        self.state_entry = self.cur_time
        self.state_entries.append(self.cur_time)
        self.state_session.append(state)

    def uniform_random(self, mean, range):
        """
            helper
        """
        return mean + 2*range*(np.random.random()-0.5)

    def loop(self):
        """
            abstract method: should be implemented in classes that extends Task

            Specs:
            It holds the task logic. After the call to the `start` function,
            the `loop` function will be called continuously.

            Returns: 2 values:
                state(boolean): indicates to continue running (`True`) or end the task (`False`)
                info(dict): a dictionary of task information that will be printed in the GUI in the format key-value
                (Note: the task information dictionary should not contain lists or arrays)
        """
        raise NotImplementedError

    def get_info(self):
        """
             abstract method: should be implemented in classes that extends Task
        """
        return {}

    def stop(self):
        """
            method to stop task: sent stop message to teensy
        """
        self.teensy.write('stop')

    def get_data(self):
        """
            callback function: is called when`Save Data` button clicked in the GUI.

            Note: data will be saved through the GUI

            Returns:
                dict: the dictionary of data to be saved  from the task
        """
        input_data = self.teensy.get_input_data()
        input_dict = {}
        for i in range(len(self.teensy.inputs)):
            input_dict[self.teensy.inputs[i]] = np.array([x[i] for x in input_data])
        return {'inputs' : input_dict,
                'outputs' : self.teensy.get_output_data()}

    def get_time_in_state(self):
        """
            returns state
        """
        return self.cur_time - self.state_entry

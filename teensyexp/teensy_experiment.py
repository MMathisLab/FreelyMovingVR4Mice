"""
GUI to run teensy experiments
    - system setup information taken from system_setup.json (which is written by system_setup.py)

GK 05/07/2019

Note(mary): API documentation added 11/08/2022
"""

import os
import sys
import shutil
import json
import pickle
import copy
from tkinter import Tk, Toplevel, Label, Button, Entry, Radiobutton, END, DISABLED, IntVar, StringVar, messagebox, \
    filedialog, simpledialog
from tkinter.ttk import Combobox
import numpy as np
import importlib.util
import inspect
import threading
import datetime
import time
from pathlib import Path

from distutils.util import strtobool
from teensyexp.teensy import Teensy
from teensyexp.helpers import process_config

class TeensyExperimentGUI(object):
    """
      Class to support Gui interface
      and orchestrate the experiment logic
    """

    def __init__(self):
        """
            class auto-constructor: loads config and initialises gui
            Note:
                class attributes for gui callback are defined locally in methods (ignored in constructor)
        """
        ### check if default path exists
        self.task_info = None
        self.unity_task = None
        self.gui_task = None
        self.task_params = None
        self.task_module = None

        path = self._get_default_path()
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok = False)

        ### load configuration from json file
        self.setup_list = self.get_setup_list()  # gui element
        self.setup = self.load_setup()
        self.window = self.create_gui()
        self.task = None
        self.teensy = None
        self.gui_on = True
        self.saved_ok = False

    def _get_default_path(self):
        """
            :priority: helpers
                This method finds the path to configs global folder précised in the local config_path.json file
            :return: normalized path to the config folder
            :rtype: string
         """
        config_path = Path("config_path.json")
        current_dir = Path.cwd()
        config_path = current_dir.joinpath(config_path)  # default class constructor input
        config_dict = process_config(config_path)
        if config_dict:
            default_path = Path(config_dict["config_path"]).resolve()
        else:
            default_path = current_dir.joinpath(Path("vr4mice/cfg"))
        return default_path

    def get_setup_file_name(self, name=''):
        """
            :priority: helpers
                This method finds the config .json file in the host FS
            :param name: name of the config file without extension, default = ""
            :type name: string
            :requirements: config .json file placed in the folder precised in the local config file
            :return: normalized path to the config file
            :rtype: string
        """
        name += ".json"
        return Path(self._get_default_path()).joinpath(name)

    def get_setup_list(self):
        """
            :priority: helpers
                This method lists all config files from the main config parent directory
            :return: list of files without extensions (potential config files)
            :rtype: list
        """
        # cfg_files = os.listdir(os.path.dirname(self.get_setup_file_name()))
        return [os.path.splitext(f)[0] for f in os.listdir(os.path.dirname(self.get_setup_file_name()))]

    def load_setup(self, name=None):
        """
            :priority: utils
                This method loads the information about user's provided setup (from the .json config file)
                to the class's :setup dictionary structure;
                it also initialises the classe's attributes (:task_dir, :rig_entry, :subject_entry, :out_dir etc.)
                if theirs values were found in the config file (means in setup dictionary structure);
                it also updates GUI elements with new config info.
            :param name: name of the config file without extension (name - not path!), default = None
            :type name: string
            :raises: TODO file not found
            :return: initialized setup structure
            :rtype: dictionary
        """
        if name is None:
            setup = {}
        else:
            setup_file = self.get_setup_file_name(name)
            if not os.path.isfile(setup_file):
                if hasattr(self, "window"):  # TODO redo hasattr approach
                    messagebox.showerror("Setup does not exist!",
                                         "This setup file does not exist, "
                                         "please create a new setup file with this name.",
                                         parent=self.window)
                    self.setup_name.set("")  # gui interaction
                    self.remove_setup(name)
                return {}

            setup = json.load(open(setup_file, 'r'))  # setup struct setter

        # import tasks and load task_list
        if 'task_dir' not in setup:
            setup['task_dir'] = ''
        if hasattr(self, 'task_dir'):
            self.task_dir.set(setup['task_dir'])  # gui interaction
        self.update_tasks(setup['task_dir'])

        # get rig info
        if 'rigs' not in setup:
            setup['rigs'] = {}
        if hasattr(self, "rig_entry"):
            self.rig_entry['values'] = tuple(setup['rigs'].keys()) + ('Add New Rig',)
            self.rig.set("" if len(setup['rigs'].keys()) == 0 else list(setup['rigs'].keys())[0])  # gui interaction

        if 'subjects' not in setup:
            setup['subjects'] = []
        if hasattr(self, "subject_entry"):
            self.subject_entry['values'] = tuple(setup['subjects'])

        if 'out_dir' not in setup:
            setup['out_dir'] = []
        if hasattr(self, "out_dir_entry"):
            self.out_dir_entry['values'] = tuple(setup['out_dir']) + ('Browse',)
            self.out_dir.set(setup['out_dir'][0] if len(setup['out_dir']) > 0 else "")  # gui interaction

        return setup

    def save_setup(self, setup=None, setup_name=None, notify=False):
        """
            :priority: utils
                This method saves setup in the .json file .
            :param setup: config structure, default = None
            :param setup_name: name of new config, default = None
            :param notify: flag to determine if the gui message is needed ,default = False
        """
        setup = self.setup if setup is None else setup
        setup_name = self.setup_name.get() if setup_name is None else setup_name  # gui interaction
        json.dump(setup, open(self.get_setup_file_name(setup_name), 'w'))  # stores in gui file
        if notify:
            messagebox.showinfo("Config Saved", "Configuration file has been saved.", parent=self.window)

    def reset_setup(self, name):
        """
        :priority: utils
            This method resets (fills with {}) the setup in the .json file
        :param name: config name to reset, default = None
        """
        self.save_setup({}, name)

    def change_setup(self, event=None):
        """
            :priority: gui callback
                This method updates the setup structure if new config file were provided by user
            :param event: default None
        """
        ret = True
        if self.setup_name.get() == 'Create New Setup':  # gui interaction
            ret = self.create_new_setup()
        if ret:
            self.setup = self.load_setup(self.setup_name.get())  # gui interaction
        else:
            self.setup_name.set("")  # gui interaction

    def create_new_setup(self):
        """
            :priority: utils
                This method allows user introduce add the new setup name (name of config file);
            it updates gui elements with new setup
            :return: True if new name was added, or False if name already exists
            :rtype: boolean
      """
        # get new setup name
        new_name = simpledialog.askstring("", "Please enter a name (no special characters).", parent=self.window)

        if new_name:
            if new_name not in self.setup_list:
                self.setup_list.append(new_name)
                self.setup_entry['values'] = tuple(self.setup_list) + ('Create New Setup',)
                self.setup_name.set(new_name)
                self.reset_setup(new_name)  # clean file?
            return True
        else:
            return False

    def remove_setup(self, name=None):
        """
            :priority: gui callback
                This method deletes the setup file from file system (attention! all information will be lost)
            :param name: name of the config file without extension (name - not path!), default = None
            :type name: string
            :raises: TODO file not found
        """
        if name is None:
            name = self.setup_name.get()  # gui interaction
        delete_setup = messagebox.askyesnocancel("Delete Setup Permanently?",
                                                 "Would you like to delete the setup permanently (yes),"
                                                 "\nremove the setup from the list for this session (no),"
                                                 "\nor neither (cancel).",
                                                 parent=self.window)
        if delete_setup is not None:  # gui interaction
            if delete_setup:
                os.remove(self.get_setup_file_name(name))
            self.setup_list.remove(name)  # gui interaction : update
            self.setup_entry['values'] = tuple(self.setup_list) + ('Create New Setup',)
            self.setup_name.set("")  # gui interaction : update
            # TODO :: reset to default drop down boxes!

    def update_tasks(self, task_dir):
        """
            :priority: gui callback
                This method dynamically loads python scripts (package) that corresponds to the tasks to execute
            :param task_dir: the path to the folder that contains new tasks package
            :type task_dir: string
            :raises AttributeError: Failed to load tasks from directory
        """
        if task_dir:
            if hasattr(self, "task_module"):
                sys.path.remove(sys.path[0])

            new_path = os.path.normpath(os.path.dirname(task_dir))
            if new_path not in sys.path:
                sys.path.insert(0, new_path)

            new_mod = os.path.basename(task_dir)
            if new_mod in sys.modules:
                del sys.modules[new_mod]

            task_spec = importlib.util.find_spec(os.path.basename(task_dir))
            try:
                self.task_module = importlib.util.module_from_spec(task_spec)
                task_spec.loader.exec_module(self.task_module)
                task_list = [t for t in dir(self.task_module) if '__' not in t]
            except AttributeError:
                if hasattr(self, "window"):
                    messagebox.showerror("Failed to load tasks!",
                                         "Failed to load tasks from directory = " + task_dir + ".\nPlease select a different directory.",
                                         parent=self.window)
                task_list = []

        else:
            task_list = []

        self.task_params = {}
        for t in task_list:
            obj = getattr(self.task_module, t)  # TODO no getattr
            args = inspect.getargspec(obj)
            self.task_params[t] = {}
            for i in range(2, len(args[0])):
                self.task_params[t][args[0][i]] = args[3][i - 2]

        if hasattr(self, 'task_entry'):  # TODO no hasattr
            self.task_name.set("")  # gui interaction : update
            self.task_entry['values'] = tuple(self.task_params.keys())

    def add_new_rig(self):
        """
            :priority: helpers
                This method provides GUI to connect the rig;
                it provides GUI input for rig-related structures (:)
            :requirements: connected rig
        """
        new_rig_gui = Toplevel(self.window)
        new_rig_gui.title("Add New Rig")

        # get serial ports with Arduino or Teensy
        from serial.tools.list_ports import comports
        ports = []
        look_for = ['USB Serial Device', 'Teensy', 'Arduino']
        for p in comports():
            if any([l in p.description for l in look_for]):
                ports.append(p[0])

        new_rig_gui.cur_row = 0

        Label(new_rig_gui, text="Rig Name: ").grid(sticky="w", row=new_rig_gui.cur_row, column=0)
        this_rig = StringVar(new_rig_gui)
        Entry(new_rig_gui, textvariable=this_rig).grid(sticky="nsew", row=new_rig_gui.cur_row, column=1)
        new_rig_gui.cur_row += 1

        Label(new_rig_gui, text="Port: ").grid(sticky="w", row=new_rig_gui.cur_row, column=0)
        this_port = StringVar(new_rig_gui)
        port_entry = Combobox(new_rig_gui, textvariable=this_port)
        port_entry['values'] = tuple(ports)
        port_entry.grid(sticky="nsew", row=new_rig_gui.cur_row, column=1)
        new_rig_gui.cur_row += 1

        Label(new_rig_gui, text="Baud Rate: ").grid(sticky="w", row=new_rig_gui.cur_row, column=0)
        this_baud = StringVar(new_rig_gui, value="115200")
        baud_entry = Combobox(new_rig_gui, textvariable=this_baud)
        baud_entry['values'] = ('9600', '14400', '19200', '28800', '38400', '57600', '115200')
        baud_entry.grid(sticky="nsew", row=new_rig_gui.cur_row, column=1)
        new_rig_gui.cur_row += 1

        Label(new_rig_gui, text="Inputs: ").grid(sticky="w", row=new_rig_gui.cur_row, column=0)
        this_inputs = StringVar(new_rig_gui)
        Entry(new_rig_gui, textvariable=this_inputs).grid(sticky="nsew", row=new_rig_gui.cur_row, column=1)
        new_rig_gui.cur_row += 1

        Label(new_rig_gui, text="").grid(sticky="w", row=new_rig_gui.cur_row, column=0)
        new_rig_gui.cur_row += 1

        def _add_teensy_output(new_rig_gui):

            Label(new_rig_gui, text="Name: ").grid(sticky="w", row=new_rig_gui.cur_row, column=0)
            new_rig_gui.output_names.append(StringVar(new_rig_gui))
            Entry(new_rig_gui, textvariable=new_rig_gui.output_names[-1]).grid(sticky="nsew", row=new_rig_gui.cur_row,
                                                                               column=1)
            new_rig_gui.cur_row += 1

            Label(new_rig_gui, text="Command: ").grid(sticky="w", row=new_rig_gui.cur_row, column=0)
            new_rig_gui.output_commands.append(StringVar(new_rig_gui))
            Entry(new_rig_gui, textvariable=new_rig_gui.output_commands[-1]).grid(sticky="nsew",
                                                                                  row=new_rig_gui.cur_row, column=1)
            new_rig_gui.cur_row += 1

            Label(new_rig_gui, text="Parameters: ").grid(sticky="w", row=new_rig_gui.cur_row, column=0)
            new_rig_gui.output_params.append(StringVar(new_rig_gui))
            Entry(new_rig_gui, textvariable=new_rig_gui.output_params[-1]).grid(sticky="nsew", row=new_rig_gui.cur_row,
                                                                                column=1)
            new_rig_gui.cur_row += 1

            Label(new_rig_gui, text="").grid(sticky="w", row=new_rig_gui.cur_row, column=0)
            new_rig_gui.cur_row += 1

        new_rig_gui.output_names = []
        new_rig_gui.output_commands = []
        new_rig_gui.output_params = []
        Label(new_rig_gui, text="Outputs: ").grid(sticky="w", row=new_rig_gui.cur_row, column=0)
        Button(new_rig_gui, text="Add Output", command=lambda: _add_teensy_output(new_rig_gui)).grid(sticky="nsew",
                                                                                                    row=new_rig_gui.cur_row,
                                                                                                    column=1)
        new_rig_gui.cur_row += 1

        Label(new_rig_gui, text="").grid(sticky="w", row=new_rig_gui.cur_row, column=0)
        new_rig_gui.cur_row += 1

        def _add_teensy_config(new_rig_gui):
            """
                callback for Submit button to add teensy config
            """
            output_dict = {'start': {'command': 'A'},
                           'stop': {'command': 'Z'},
                           'reboot': {'command': 'Y'}}

            for i in range(len(new_rig_gui.output_names)):
                output_dict[new_rig_gui.output_names[i].get()] = {}
                output_dict[new_rig_gui.output_names[i].get()]['command'] = new_rig_gui.output_commands[i].get()
                if new_rig_gui.output_params[i].get():
                    output_dict[new_rig_gui.output_names[i].get()]['params'] = new_rig_gui.output_params[i].get().split(
                        ',')

            self.setup['rigs'][this_rig.get()] = {'port': this_port.get(),
                                                  'baudrate': this_baud.get(),
                                                  'inputs': this_inputs.get().split(','),
                                                  'outputs': output_dict}
            self.rig_entry['values'] = tuple(self.setup['rigs'].keys()) + ('Add New Rig',)
            self.rig.set(this_rig.get())

            if messagebox.askyesno("Save New Rig?", "Would you like to save the new rig to the configuration file?",
                                   parent=self.window):
                self.save_setup()
            new_rig_gui.destroy()

        Button(new_rig_gui, text="Submit", command=lambda: _add_teensy_config(new_rig_gui)).grid(sticky="nsew", row=100,
                                                                                                 column=1)
        Button(new_rig_gui, text="Cancel", command=new_rig_gui.destroy).grid(sticky="nsew", row=101, column=1)

    def connect_teensy(self):
        """
            :priority: gui callback
                This method adds new rig (teensy) to the system according to the input from GUI
                If teensy already connected it disconnects it and connects the new rig
                The creation and initialisation of Teensy object happens here!
        """
        if self.rig.get() == 'Add New Rig':  # gui interaction
            self.add_new_rig()
            return

        if self.teensy:
            if messagebox.askyesno("Already Connected!", "Already connected to: " + self.rig_label[
                'text'] + ".\nWould you like to close this connection and connect to: " + self.rig.get() + "?",
                                   parent=self.window):
                self.disconnect_teensy()
            else:
                return

        teensy_info = self.setup['rigs'][self.rig.get()]
        self.teensy = Teensy(teensy_info['port'], teensy_info['baudrate'], teensy_info['inputs'],
                             teensy_info['outputs'])
        self.rig_label['text'] = self.rig.get()

    def disconnect_teensy(self):
        """
            :priority: gui callback
                This method disconnects teensy and closes communication protocol
        """
        if self.teensy:
            self.teensy.close()
            self.teensy = None
            self.rig_label['text'] = "Not Connected"
        # TODO delete Teensy instance

    def add_sub_to_cfg(self):
        """
            :priority: gui callback
                This method adds new subject (experimentator/user) to the system
                and updates the config file
        """
        self.setup['subjects'].append(self.subject.get())  # gui interaction
        self.subject_entry['values'] = tuple(self.setup['subjects'])
        self.save_setup()

    def rm_sub_from_cfg(self):
        """
            :priority: gui callback
                This method removes new subject (experimentator/user) to the system
                and updates the config file
        """
        self.setup['subjects'].remove(self.subject.get())
        self.subject_entry['values'] = tuple(self.setup['subjects'])
        self.subject.set("")
        self.save_setup()

    def browse_out_dir(self, event=None):
        """
            :priority: gui callback
                This method adds the new directory for output (via GUI)
        """
        if self.out_dir.get() == "Browse":
            new_dir = filedialog.askdirectory(parent=self.window, title="Select Save Directory")
            if new_dir:
                self.setup['out_dir'].append(new_dir)
                self.out_dir_entry['values'] = tuple(self.setup['out_dir']) + ('Browse',)
                self.out_dir.set(new_dir)
                self.save_setup()
            else:
                self.out_dir.set("")

    def rm_out_dir(self):
        """
            :priority: gui callback
                This method remove path to storage from the app (via GUI)
        """
        self.setup['out_dir'].remove(self.out_dir.get())
        self.out_dir_entry['values'] = tuple(self.setup['out_dir']) + ('Browse',)
        self.out_dir.set("")
        self.save_setup()

    def browse_task_dir(self):
        """
            :priority: utils
                This method adds path to tasks folder (via GUI)
                and dynamically loads the task's module;
                it updates the .json config file
        """
        new_dir = filedialog.askdirectory(parent=self.window, title="Select Task Directory")
        if new_dir:
            if new_dir != self.task_dir.get():
                self.setup['task_dir'] = new_dir
                self.task_dir.set(new_dir)
                self.update_tasks(new_dir)
                self.save_setup()

    def submit_params(self, window, entries):
        """
            callback method of _create_param_gui
        """
        index = 0
        for key, value in self.task_params[self.task_name.get()].items():
            if value is not None:
                convert_type = type(value) if type(value) is not list else type(value[0])
                split_entries = entries[index].get().split(',')
                if (len(split_entries) > 1) or (type(value) is list):
                    if convert_type is bool:
                        self.task_params[self.task_name.get()][key] = np.array([strtobool(s) for s in split_entries],
                                                                               dtype=convert_type).tolist()
                    else:
                        self.task_params[self.task_name.get()][key] = np.array(split_entries,
                                                                               dtype=convert_type).tolist()
                else:
                    if convert_type is bool:
                        self.task_params[self.task_name.get()][key] = convert_type(strtobool(split_entries[0]))
                    else:
                        self.task_params[self.task_name.get()][key] = convert_type(split_entries[0])
                index += 1
        window.quit()
        window.destroy()

    def _create_param_gui(self):
        """
            inner method used in edit_task
        """
        window = Toplevel(self.window)
        window.title(self.task_name.get() + " -- enter parameters")

        cur_row = 0
        cur_col = 0
        cur_col = 0
        entry_vars = []
        entries = []
        for key, value in self.task_params[self.task_name.get()].items():
            if value != None:
                if (cur_row + 1) % 15 == 0:
                    cur_col += 2
                    cur_row = 0
                entry_vars.append(StringVar())
                Label(window, text=key + ": ").grid(sticky="n", row=cur_row, column=cur_col)
                entries.append(Entry(window, textvariable=entry_vars[-1]))
                if type(value) is list:
                    entries[-1].insert(END, ','.join([str(v) for v in value]))
                else:
                    entries[-1].insert(END, str(value))
                entries[-1].grid(sticky="nsew", row=cur_row, column=cur_col + 1)
                cur_row += 1

        Button(window, text="Submit", command=lambda: self.submit_params(window, entries)).grid(sticky="nsew",
                                                                                                row=cur_row,
                                                                                                column=cur_col,
                                                                                                columnspan=2)
        return window

    def edit_task(self):
        """
            :priority: gui callback
                This method verify if the task's package was selected (via GUI)
            and initialize the parameters tasks;
        """
        if self.task_name.get():  # gui interaction
            param_gui = self._create_param_gui()
        else:
            messagebox.showerror("No Task", "No task selected. Please select a task first.", parent=self.window)

    def init_task(self):
        """
            :priority: gui callback
                This method initialises the task via extracting of information from the uploaded task's plugin files,
                it defines the type of task (gui, unity etc.)
                The initialization happens only in case when the rig is connected and
                there is no other running task (system is free)
        """
        if not self.teensy:
            messagebox.showerror("No Rig!",
                                 "The rig has not been initialized.\nPlease connect to the rig before starting the task!",
                                 parent=self.window)
            self.task_on.set(0)
        elif self.task_on_button:
            messagebox.showerror("Task Running!",
                                 "A task is currently running.\nPlease stop the current task before preparing another one.",
                                 parent=self.window)
            self.task_on.set(1)
        else:
            task_object = getattr(self.task_module, self.task_name.get())
            task_params = copy.deepcopy(self.task_params[self.task_name.get()])
            self.task = task_object(self.teensy, **task_params)
            parent_class = [c.__name__ for c in self.task.__class__.__mro__]
            self.gui_task = True if 'GuiTask' in parent_class else False
            self.unity_task = True if 'UnityTask' in parent_class else False
            self.task_label['text'] = self.task_name.get()
            self.task_on.set(-1)

            try:
                self._reset_progress_labels()
            except:
                pass
            finally:
                self.info_labels = []
                self.value_labels = []
                self.task_info = self.task.get_info()
                self.check_task_progress()

    def check_task_progress(self, info=None):
        """
            :priority: utils
                This method allows track the state of task in real time on gui
                get information from task_info dictionary
        """
        if info is None:
            info = self.task_info

        index = 0
        if len(self.info_labels) == 0:
            for k, v in info.items():
                self.info_labels.append(Label(self.window, text=k + ': '))
                self.info_labels[-1].grid(row=self.next_row + index, column=0)
                self.value_labels.append(Label(self.window, text=str(v)))
                self.value_labels[-1].grid(row=self.next_row + index, column=1)
                index += 1
        else:
            for k, v in info.items():
                self.value_labels[index]['text'] = str(v)
                index += 1

        # if not initial:
        #     if self.task_on_button:
        #         self.window.after(1, self.check_task_progress)
        #     else:
        #         self.task_on.set(0)
        #         if self.gui_task:
        #             self.task.window.destroy()

    def _reset_progress_labels(self):
        """
            inner method for init_task
            cleans labels
        """
        index = 0
        while index < len(self.info_labels):
            self.info_labels[index].destroy()
            self.value_labels[index].destroy()
            index += 1

    def run_task_on_thread(self):
        """
            :priority: threads job
                This method is a wrapper of the thread's job
                it controls the end and start of job from inside in function
                of execution time and state of gui's control button
        """

        self.task.start()
        exec_time = .001
        loop_time = 0
        continue_task = True
        while continue_task and self.task_on_button:
            curr_time = time.time()
            if curr_time > loop_time + exec_time:
                loop_time = curr_time
                continue_task, self.task_info = self.task.loop()

        self.task.stop()
        self.task_on_button = False

    def no_task_window(self, start_button=True):
        """
        :priority: callback gui
            This method shows the message for uninitialized task
        :param start_button: flag for button start
        :type start_button: boolean
        """
        self.task_on.set(0)
        if start_button:
            txt = "A task has not been initialized.\nPlease select a task before starting the session."
        else:
            txt = "A task has not been initialized.\nPlease select a task and run a session before trying to save data."
        messagebox.showerror("No Task", txt, parent=self.window)

    def run_task(self):
        """
        :priority: callback gui
            This method shows the message for uninitialized task
        :param start_button: flag for button start
        :type start_button: boolean
        """
        if not self.task_on_button:
            if (self.task is None) | (self.task_on.get() == 0):
                self.no_task_window()
            else:
                self.task_on_button = True
                if self.gui_task:
                    self.task.window = self.task.create_gui(self.window)
                self.task_thread = threading.Thread(target=self.run_task_on_thread).start()
                self.check_task_progress()

    def stop_task(self):
        """
            method that is callback of stop button
            updates task_on_button current class attributed that indicates if there is a running task
            destroys gui window
        """
        self.task_on_button = False
        if self.gui_task:
            self.task.window.destroy()

    def _dump_data(self, data_to_save, filename):
        """
            inner method for save_data
            update saved_ok flag, that checked on exit

            Args:
                data_to_save: output form task (return of self.task.get_data())
                filename(str): path and name of file to save
        """
        pickle.dump(data_to_save, open(filename, 'wb'))
        messagebox.showinfo("File Saved", "File saved to %s" % filename, parent=self.window)
        self.saved_ok = True

    def add_note(self):
        """
            currently not used
        """
        add_note_window = Toplevel(self.window)
        note = StringVar(add_note_window)
        Label(add_note_window, txt="Session Note:").pack()
        Entry(add_note_window, textvariable=note).pack()
        Button(add_note_window, text="Submit", command=lambda: add_note_window.quit()).pack()
        add_note_window.mainloop()
        note = note.get()
        add_note_window.destroy()
        return note

    def save_data(self):
        """
            method to save data

            Warnings:
                if file already exists
            Note:
                for unity task saves to default_path/tmp/unity_video.avi (avi video format)
        """
        if self.task is None:
            self.no_task_window(False)
        else:
            dir = self.out_dir.get()
            if not os.path.isdir(dir):
                os.makedirs(dir)
            sub = self.subject.get()
            date = datetime.datetime.today()
            yyyy = str(date.year)
            mm = str(date.month) if date.month >= 10 else '0' + str(date.month)
            dd = str(date.day) if date.day >= 10 else '0' + str(date.day)
            filename = os.path.normpath(
                dir + '/' + sub + '_' + yyyy + '-' + mm + '-' + dd + '_' + self.attempt.get() + '.pickle')
            data_to_save = self.task.get_data()
            # data_to_save.update(session_note=note)
            if os.path.isfile(filename):
                if not messagebox.askyesno("File Already Exists",
                                           "File %s already exists!\nWould you like to overwrite this file?\nIf no, you can change attempt number and click save again." % filename,
                                           parent=self.window):
                    return
            self._dump_data(data_to_save, filename)

            if self.unity_task:
                tmp_file = os.path.normpath(self._get_default_path() + '/tmp/unity_video.avi')
                if os.path.isfile(tmp_file):
                    video_file = filename.replace('.pickle', '_video.avi')
                    shutil.move(tmp_file, video_file)

    def check_close(self):
        """
            method used for close bottom callback
            checks if there is a running task and if all data saved
        """
        if self.task_on.get():
            messagebox.showerror("Task Open", "Task is currently open. Please stop task before closing.",
                                 parent=self.window)
        else:
            if not self.saved_ok:
                if messagebox.askokcancel("Exit", "ARE YOU SURE YOU SAVED YOUR Data?"):
                    self.gui_on = False

    def close_window(self):
        """
            method to close gui window properly
            closes teensy connection before quit
        """
        try:
            if self.teensy:
                self.teensy.close()
        except Exception as e:
            print(e)
        finally:
            self.window.quit()
            self.window.destroy()

    def create_gui(self):
        """
            method that generates all gui components and defines associated callbacks
            Note: most of class attributes are defines here locally

        """
        window = Tk()
        window.title("Teensy Experiment")
        cur_row = 0
        combobox_width = 15

        # select cfg file
        if len(self.setup_list) > 0:
            initial_setup = self.setup_list[0]
        else:
            initial_setup = ""

        Label(window, text="Config: ").grid(row=cur_row, column=0)
        self.setup_name = StringVar(window, value=initial_setup)
        self.setup_entry = Combobox(window, textvariable=self.setup_name, width=combobox_width)
        self.setup_entry['values'] = tuple(self.setup_list) + ('Create New Setup',)
        self.setup_entry.bind("<<ComboboxSelected>>", self.change_setup)
        self.setup_entry.grid(sticky="nsew", row=cur_row, column=1)
        Button(window, text="Remove Setup", command=self.remove_setup).grid(sticky="nsew", row=cur_row, column=2)

        if os.path.isfile(self.get_setup_file_name(initial_setup)):
            self.change_setup(initial_setup)
        cur_row += 1

        # empty line
        cur_row += 1

        # connect to rig
        if len(self.setup['rigs'].keys()) > 0:
            initial_rig = list(self.setup['rigs'].keys())[0]
        else:
            initial_rig = ""

        Label(window, text="Rig: ").grid(row=cur_row, column=0)
        self.rig = StringVar(window, value=initial_rig)
        self.rig_entry = Combobox(window, textvariable=self.rig, width=combobox_width)
        self.rig_entry['values'] = tuple(self.setup['rigs'].keys()) + ('Add New Rig',)
        self.rig_entry.grid(sticky="nsew", row=cur_row, column=1)
        Button(window, text="Connect", command=self.connect_teensy).grid(sticky="nsew", row=cur_row, column=2)
        cur_row += 1

        Label(window, text="Current Rig: ").grid(row=cur_row, column=0)
        self.rig_label = Label(window, text="Not Connected")
        self.rig_label.grid(sticky="nsew", row=cur_row, column=1)
        Button(window, text="Disconnect", command=self.disconnect_teensy).grid(sticky="nsew", row=cur_row, column=2)
        cur_row += 1

        # Empty line
        cur_row += 1

        # select subject
        Label(window, text="Subject: ").grid(sticky="n", row=cur_row, column=0)
        self.subject = StringVar(window)
        self.subject_entry = Combobox(window, textvariable=self.subject, width=combobox_width)
        self.subject_entry['values'] = tuple(self.setup['subjects'])
        self.subject_entry.grid(sticky="nsew", row=cur_row, column=1)
        Button(window, text="Add Subject", command=self.add_sub_to_cfg).grid(sticky="nsew", row=cur_row, column=2)
        Button(window, text="Remove Subject", command=self.rm_sub_from_cfg).grid(sticky="nsew", row=cur_row + 1,
                                                                                 column=2)
        cur_row += 1

        # select attmept
        Label(window, text="Attempt: ").grid(sticky="n", row=cur_row, column=0)
        self.attempt = StringVar(window)
        self.attempt_entry = Combobox(window, textvariable=self.attempt, width=combobox_width)
        self.attempt_entry['values'] = tuple(range(1, 10))
        self.attempt_entry.current(0)
        self.attempt_entry.grid(sticky="nsew", row=cur_row, column=1)
        cur_row += 1

        # select data directory
        Label(window, text="Save Dir: ").grid(row=cur_row, column=0)
        self.out_dir = StringVar(window)
        self.out_dir_entry = Combobox(window, textvariable=self.out_dir, width=combobox_width)
        self.out_dir_entry['values'] = ('', 'Browse') if len(self.setup['out_dir']) == 0 else tuple(
            self.setup['out_dir']) + ('Browse',)
        self.out_dir_entry.current(0)
        self.out_dir_entry.bind("<<ComboboxSelected>>", self.browse_out_dir)
        self.out_dir_entry.grid(sticky="nsew", row=cur_row, column=1)
        # Button(window, text="Browse", command=self.browse_out_dir).grid(sticky="nsew", row=cur_row, column=2)
        Button(window, text="Remove Dir", command=self.rm_out_dir).grid(sticky="nsew", row=cur_row, column=2)
        cur_row += 1

        # 2 empty lines
        cur_row += 2

        # select and initialize task
        Label(window, text="Task Dir: ").grid(row=cur_row, column=0)
        self.task_dir = StringVar(window, value=self.setup['task_dir'])
        Entry(window, textvariable=self.task_dir).grid(sticky="nsew", row=cur_row, column=1)
        Button(window, text="Browse", command=self.browse_task_dir).grid(sticky="nsew", row=cur_row, column=2)
        cur_row += 1

        Label(window, text="Task: ").grid(sticky="n", row=cur_row, column=0)
        self.task_name = StringVar(window)
        self.task_entry = Combobox(window, textvariable=self.task_name, width=combobox_width)
        self.task_entry['values'] = tuple(self.task_params.keys())
        self.task_entry.grid(sticky="nsew", row=cur_row, column=1)
        Button(window, text="Edit Task", command=self.edit_task).grid(sticky="nsew", row=cur_row, column=2)
        cur_row += 1

        # Button(window, text="Init Task", command=self.init_task).grid(sticky="nsew", row=cur_row, column=2)
        Label(window, text="Current Task: ").grid(row=cur_row, column=0)
        self.task_label = Label(window, text="No Task")
        self.task_label.grid(sticky="nsew", row=cur_row, column=1)
        cur_row += 1

        # empty line
        cur_row += 1

        # start and stop task
        self.task_on_button = False
        self.task_on = IntVar(window, value=0)
        Radiobutton(window, text="Ready", indicatoron=0, variable=self.task_on, value=-1, command=self.init_task).grid(
            sticky="nsew", row=cur_row, column=1)
        cur_row += 1
        Radiobutton(window, text="Start", indicatoron=0, variable=self.task_on, value=1, command=self.run_task).grid(
            sticky="nsew", row=cur_row, column=1)
        cur_row += 1
        Radiobutton(window, text="Stop", indicatoron=0, variable=self.task_on, value=0, command=self.stop_task).grid(
            sticky="nsew", row=cur_row, column=1)
        cur_row += 1

        # Empty line
        cur_row += 1

        # save data
        Button(window, text="Save Task Data", command=self.save_data).grid(sticky="nsew", row=cur_row, column=1,
                                                                           columnspan=1)
        cur_row += 1

        # Empty line
        cur_row += 1

        # close
        # Button(window, text="Close", command=lambda: setattr(self, "gui_on", False)).grid(sticky="nsew", row=cur_row, column=1, columnspan=1)
        Button(window, text="Close", command=self.check_close).grid(sticky="nsew", row=cur_row, column=1, columnspan=1)
        cur_row += 1

        # configure size of empty rows
        col_count, row_count = window.grid_size()
        for r in range(row_count):
            window.grid_rowconfigure(r, minsize=20)

        self.next_row = cur_row + 1
        return window

    def run_experiment(self):
        """
            method calls the check of task progress for current task;
            updates window if new task is detected
        """
        print_delay = .01
        last_print = time.time()

        while self.gui_on:
            curr_time = time.time()
            if self.task_on_button:
                if curr_time - last_print > print_delay:
                    self.check_task_progress()
                    last_print = curr_time
            elif self.task_on.get() == 1:
                self.task_on.set(0)
                if self.gui_task:
                    self.task.window.destroy()

            self.window.update()

        self.close_window()


def main():
    """
        program main entry point
    """
    exp = TeensyExperimentGUI()
    exp.run_experiment()


#__name__ == '__main__'
#main()
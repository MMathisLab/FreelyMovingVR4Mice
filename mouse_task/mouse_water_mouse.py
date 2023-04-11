import time
import threading
from teensyexp.tasks_abc.gui_task import GuiTask
from tkinter import Tk, Toplevel, Label, Entry, Button, Radiobutton, IntVar, BooleanVar, StringVar


class water_mouse(GuiTask):
    def __init__(self, teensy):
        super().__init__(teensy)
        self.current_reward = 1000
        self.teensy.write('r_water', [self.current_reward])
        self.teensy.write('l_water', [self.current_reward])
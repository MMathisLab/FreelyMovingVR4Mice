'''
Task to prime (or clean) water line

GK 05/24/19
'''

from teensyexp.tasks_abc import GuiTask
from tkinter import Tk, Toplevel, Label, Entry, Button, Radiobutton, IntVar, BooleanVar, StringVar
import time
import threading


class ManualWater(GuiTask):


    def __init__(self, teensy):
        super().__init__(teensy)
        self.keep_going = True
        self.n_delivered = 0


    def deliver_water(self):

        if self.n_delivered < self.current_pulses:
            self.teensy.write('water', [self.current_reward])
            self.n_delivered += 1

            if self.continuous.get():
                self.window.after(self.wait, self.deliver_water)
            else:
                self.n_delivered = 0
        else:
            self.n_delivered = 0


    def close(self):
        self.keep_going = False


    def change_rate(self, var, idx, mode):
        try:
            self.current_rate = float(self.rate.get())
            self.get_wait()
        except Exception:
            pass


    def change_reward(self, var, idx, mode):
        try:
            self.current_reward = int(self.reward.get())
            self.get_wait()
        except Exception:
            pass


    def change_pulse(self, var, idx, mode):
        try:
            self.current_pulses = int(self.n_pulses.get())
        except Exception:
            pass


    def get_wait(self):
        self.wait = int((1000 / self.current_rate) - self.current_reward)


    def create_gui(self, parent):

        window = Toplevel(parent)
        window.title("Manual Water Delivery")
        cur_row = 0

        Label(window, text="Pump Time (ms): ").grid(row=cur_row, column=0)
        self.reward = IntVar(window, value=250)
        self.current_reward = self.reward.get()
        self.reward.trace_add("write", self.change_reward)
        Entry(window, textvariable=self.reward).grid(row=cur_row, column=1)
        cur_row += 1

        Label(window, text="Continuous Rate (Hz): ").grid(row=cur_row, column=0)
        self.rate = StringVar(window, value="2")
        self.current_rate = float(self.rate.get())
        self.get_wait()
        self.rate.trace_add("write", self.change_rate)
        Entry(window, textvariable=self.rate).grid(row=cur_row, column=1)
        cur_row += 1

        Label(window, text="Number of Pulses: ").grid(row=cur_row, column=0)
        self.n_pulses = StringVar(window, value="1")
        self.current_pulses = int(self.n_pulses.get())
        self.n_pulses.trace_add("write", self.change_pulse)
        Entry(window, textvariable=self.n_pulses).grid(row=cur_row, column=1)
        cur_row += 1

        Button(window, text="Deliver One Pulse", command=self.deliver_water).grid(row=cur_row, column=0, rowspan=2)
        self.continuous = BooleanVar(window, value=False)
        self.continuous_water = False
        Radiobutton(window, text="Continuous On", indicatoron=0, variable=self.continuous, value=True, command=self.deliver_water).grid(sticky="nsew", row=cur_row, column=1)
        Radiobutton(window, text="Continuous Off", indicatoron=0, variable=self.continuous, value=False, command=lambda: setattr(self, 'continuous_water', False)).grid(sticky="nsew", row=cur_row+1, column=1)
        cur_row += 2

        Button(window, text="Close", command=self.stop).grid(row=cur_row, column=0, columnspan=2)

        self.window = window
        return window


    def loop(self):
        return self.keep_going, {}


    def stop(self):
        self.continuous_water = False
        self.keep_going = False
        super().stop()

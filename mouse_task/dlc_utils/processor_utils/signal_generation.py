import numpy as np
import time

def get_signal(signal_type, curr_time, curr_signal, st, freq, delay):
    if signal_type == "pulse":
        curr_signal = get_nhz_pulse(
            curr_time=curr_time, st=st, freq=freq, delay=delay
        )
    if signal_type == "sin":
        curr_signal = get_sin_wave(
            curr_time=curr_time, st=st, freq=freq, delay=delay
        )
    if signal_type == "flip":
        curr_signal = flip_every_frame(curr_time=curr_time, curr_signal=curr_signal, st=st, delay=delay)
    return curr_signal

def get_nhz_pulse(curr_time, st, freq, delay):
    if (curr_time - st) < delay:
        curr_signal = 0
    else:
        curr_signal = (np.sign(np.sin(freq * np.pi * time.time())) + 1) / 2
    
    return curr_signal

def get_sin_wave(curr_time, st, delay, freq):
    if (curr_time - st) < delay:
        curr_signal = 0
    else:
        curr_signal = np.round((np.sin((curr_time * freq)) + 1) / 4, 4)
    return curr_signal

def flip_every_frame(curr_signal, curr_time, st, delay):
    if (curr_time - st) < delay:
        curr_signal = 0
    else:
        if curr_signal == 0:
            curr_signal = 1
        else:
            curr_signal = 0
    return curr_signal
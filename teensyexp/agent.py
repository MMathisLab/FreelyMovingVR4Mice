"""
Fake Teensy (Agent) controller for experiments
    -inputs and outputs are defined in system_setup.json (created using system_setup.py)
    -consistently reads inputs over serial port at sampling rate defined by teensy
    -writes output over serial on command

GK 05/07/2019
"""

import os
import numpy as np
import serial
import time
import threading
import struct


class Agent(object):
    """
    class representing teensy microcontroller
    """

    def __init__(self):
        """
        Teensy class constructor

        Args:
            serial_port
            baudrate
            inputs
            outputs
        """
        pass

    def connect_serial(self):
        """
        method initiates serial communication protocol and reset buffer
        default timeout = 0
        Exceptions:
            ignored
        """
        pass

    def read_on_thread(self):
        pass

    def start_read_buffer(self):
        """
        method that starts the reader thread (reader for serial buffer), writer for (input_data)
        saves the time of start
        """
        pass

    def read(self, index=-1, input=None):
        """
        method that used externally to read the input_data buffer filled by thread
        copies the element of input_data list to return_data dictionary
        Args:
            index: precise the minimum length to ignore
            input: set to None to ignore input if empty (<1)
                    or precise the dictionary key to fetch from input_data
        Returns:
            -1 if buffer is empty and input args is set to None returns -1
            {} if buffer is empty and input args is not None empty dictionary
            dictionary with all data
            dictionary corresponding to key
        """
        pass

    def write(self, output, params=[]):
        """
        method to write a command to the serial port buffer, use flush
        encode command from outputs list of commands as well as parameters
        Args:
            output: command to perform
            params: arguments for command
        Note:
             Writes a command to the teensy as a string of bytes.
             The first byte written is the command corresponding to the specified output
             (as setup in the teensy configuration), followed by each value in params
             (converted from 16-bit integer to 2 bytes).
        Examples:
            teensy.write('water', [100]): turns on water for 100,
            will write (from python syntax): `b'W'+struct.pack('h', 100)`
        """
        pass

    def stop(self):
        """
        change the reading class attribute to False (switch flag)
        """
        pass

    def get_input_data(self, format="array"):
        """
        Attr:
            format: ignored
        returns:
            input_data list as a numpy array
        """
        pass

    def get_output_data(self):
        """
        Returns:
            output_data list
        """
        pass

    def reset(self):
        """
        reset to empty list input_data and output_data attributes
        """
        pass

    def close(self):
        """
        stop serial communication and update reading state attribute to False via stop()
        """
        pass

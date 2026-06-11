"""
Teensy controller for experiments
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

class Teensy(object):
    """
        class representing teensy microcontroller
    """
    def __init__(self, serial_port, baudrate, inputs, outputs):
        """
            Teensy class constructor

            Args:
                serial_port
                baudrate
                inputs
                outputs
        """
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.end_bytes = struct.pack('hh', -32767, 32767)
        self.connect_serial()

        self.inputs = inputs
        self.n_inputs = len(self.inputs)
        self.outputs = outputs
        self.input_data = []
        self.output_data = []

        if  self.n_inputs > 0:
            self.start_read_buffer()

    def connect_serial(self):
        """Initiates serial communication protocol and reset buffer.
            
            default timeout = 0
            
            Exceptions:
                ignored
        """
        connected = False
        while not connected:
            try:
                self.ser = serial.Serial(self.serial_port, self.baudrate, timeout=0)
                connected = True
            except serial.SerialException:
                pass
        self.ser.reset_input_buffer()

    def read_on_thread(self):
        buffer = None
        delta = 1
        while self.reading:
            if self.ser.inWaiting() > delta:
                if buffer:
                    buffer = buffer + self.ser.read()
                else:
                    buffer = self.ser.read()
                if self.end_bytes in buffer:
                    lines = buffer.split(self.end_bytes)
                    buffer = lines[-1]
                    this_read = struct.unpack('h' * self.n_inputs, lines[-2])
                    self.input_data.append(list((time.time(),) + this_read))
 
    def start_read_buffer(self):
        """
            method that starts the reader thread (reader for serial buffer), writer for (input_data)
            saves the time of start
        """
        self.start_read_time = time.time()
        self.reading = True
        threading.Thread(target=self.read_on_thread, daemon=True).start()

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
        if abs(index) > len(self.input_data):
            if input is None:
                return {}
            else:
                return -1

        keys = ['time']+self.inputs
        vals = self.input_data[index]
        return_dict = {}
        for i in range(len(keys)):
            return_dict[keys[i]] = vals[i]

        if input is None:
            return return_dict
        else:
            return return_dict[input]

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
        if type(params) is not list:
            params = [params]

        if 'params' in self.outputs[output]:
            if len(params) != len(self.outputs[output]['params']):
                print("WARNING :: command = %s not sent; did not provide the correct number of parameters.\nParam needed = %d, param given = %d" % (output, len(self.outputs[output]['params']), len(params)))
                return

        self.output_data.append([time.time(), output] + params)
        command = self.outputs[output]['command'].encode()
        for i in range(len(params)):
            command += struct.pack('h', params[i])
        self.ser.write(command)
        self.ser.flush()

    def stop(self):
        """
            change the reading class attribute to False (switch flag)
        """
        self.reading = False

    def get_input_data(self, format='array'):
        """
            Attr:
                format: ignored
            returns:
                input_data list as a numpy array
        """
        return np.array(self.input_data)

    def get_output_data(self):
        """
        Returns:
            output_data list
        """
        return self.output_data

    def reset(self):
        """
            reset to empty list input_data and output_data attributes
        """
        self.input_data = []
        self.output_data = []

    def close(self):
        """
            stop serial communication and update reading state attribute to False via stop()
        """
        self.stop()
        self.ser.close()

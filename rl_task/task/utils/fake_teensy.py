"""Test stub for the Teensy microcontroller interface.

This class mimics the methods of the real Teensy integration used in the
Unity task code so that the RL training stack can run without hardware.
"""


class FakeTeensy(object):
    """Minimal no-op stand-in for a Teensy device."""

    def __init__(self, serial_port=None, baudrate=None, inputs=None, outputs=None):
        pass

    def connect_serial(self):
        pass

    def read_on_thread(self):
        pass

    def start_read_buffer(self):
        pass

    def read(self, index=None, input=None):
        pass

    def write(self, output=None, params=None):
        pass

    def stop(self):
        pass

    def get_input_data(self, format=None):
        pass

    def get_output_data(self):
        pass

    def reset(self):
        pass

    def close(self):
        pass

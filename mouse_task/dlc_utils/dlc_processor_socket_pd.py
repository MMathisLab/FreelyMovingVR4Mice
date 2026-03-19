import numpy as np

from typing import Any, Dict

from latency_tests.Teensy_latency.TeensyLatency import TeensyLatency
from dlc_utils.dlc_processor_socket import MyProcessor_socket


class dlc_inference_w_pd(MyProcessor_socket):
    def __init__(
        self,
        com="COM3",
        baudrate=9600,
        signal_delay=10,
        signal_type="pulse_geo",
        freq=5,
        use_teensy=1,
    ):
        super().__init__(signal_delay=signal_delay, signal_type=signal_type, freq=freq)

        self.use_teensy = use_teensy
        if self.use_teensy == 1:
            self.teensy = TeensyLatency(com, baudrate=baudrate)
            print("Using Teensy")

    def save_latency_data(self) -> Dict[str, Any]:
        """Extend parent's save_latency_data with photodiode and signal metadata."""
        if self.use_teensy == 1:
            print("Closing serial connection to teensy")
            self.teensy.close_serial()

        # Get parent's data
        save_dict = super().save_latency_data()

        # Add signal metadata
        save_dict["signal_type"] = self.signal_type
        save_dict["signal_delay"] = self.signal_delay

        # Add photodiode data if available
        if self.use_teensy == 1:
            save_dict["photodiode_read"] = np.array(self.teensy.input_data)
            save_dict["photodiode_time"] = np.array(self.teensy.input_data_time)

        return save_dict

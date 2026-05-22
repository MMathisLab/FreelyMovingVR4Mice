"""Sync photodiode processor that reuses the shared DLC/socket behavior."""

from typing import Any, Dict

import numpy as np

from dlc_utils.dlc_processor_socket_pd import dlc_inference_w_pd
from latency_tests.Teensy_latency.TeensyLatencySync import TeensyLatency


class DLCInferenceWithPhotodiodeTTL(dlc_inference_w_pd):
    def __init__(
        self,
        com="COM3",
        baudrate=9600,
        signal_delay=10,
        signal_type="pulse_geo",
        freq=5,
        use_teensy=1,
    ):
        super().__init__(
            com=com,
            baudrate=baudrate,
            signal_delay=signal_delay,
            signal_type=signal_type,
            freq=freq,
            use_teensy=use_teensy,
        )

    def _create_teensy(self, com, baudrate):
        return TeensyLatency(com, baudrate=baudrate)

    def save_latency_data(self) -> Dict[str, Any]:
        save_dict = super().save_latency_data()

        if self.use_teensy == 1:
            save_dict["ttl_read"] = np.array(getattr(self.teensy, "input_data_ttl", []))
            save_dict["teensy_time"] = np.array(
                getattr(self.teensy, "input_data_teensy_time", [])
            )

        return save_dict

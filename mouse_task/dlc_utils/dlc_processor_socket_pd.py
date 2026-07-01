import numpy as np
import importlib.util
import sys
from pathlib import Path

from typing import Any, Dict
from dlclivegui.processors import PROCESSOR_REGISTRY, register_processor

try:
    from latency_tests.Teensy_latency.TeensyLatency import TeensyLatency
except ModuleNotFoundError:
    TeensyLatency = None

try:
    from dlc_utils.dlc_processor_socket import MyProcessor_socket
except ModuleNotFoundError:
    _local_path = Path(__file__).with_name("dlc_processor_socket.py")
    _local_name = "dlclivegui_plugins.local_dlc_processor_socket"
    _spec = importlib.util.spec_from_file_location(_local_name, _local_path)
    if _spec is None or _spec.loader is None:
        raise ImportError(f"Could not import MyProcessor_socket from {_local_path}")
    _module = sys.modules.get(_local_name)
    if _module is None:
        _module = importlib.util.module_from_spec(_spec)
        sys.modules[_local_name] = _module
        _spec.loader.exec_module(_module)
    MyProcessor_socket = _module.MyProcessor_socket

PROCESSOR_REGISTRY.pop("dlc_inference_w_pd", None)


@register_processor
class dlc_inference_w_pd(MyProcessor_socket):
    PROCESSOR_NAME = "SocketProcessorWithPD"
    PROCESSOR_DESCRIPTION = "Socket processor with optional Teensy photodiode capture."
    PROCESSOR_PARAMS = {
        "com": {
            "type": "str",
            "default": "COM3",
            "description": "Serial port used for Teensy.",
        },
        "baudrate": {
            "type": "int",
            "default": 9600,
            "description": "Teensy serial baudrate.",
        },
        "signal_delay": {
            "type": "float",
            "default": 10,
            "description": "Delay in seconds before TTL signal starts.",
        },
        "signal_type": {
            "type": "str",
            "default": "pulse_geo",
            "description": "Signal mode: pulse, pulse_geo, sin, or flip.",
        },
        "freq": {
            "type": "float",
            "default": 5,
            "description": "Signal frequency in Hz.",
        },
        "use_teensy": {
            "type": "bool",
            "default": True,
            "description": "Enable Teensy photodiode acquisition.",
        },
    }

    def _create_teensy(self, com, baudrate):
        if TeensyLatency is None:
            raise ImportError(
                "TeensyLatency dependency is unavailable. Ensure mouse_task is on PYTHONPATH "
                "and Teensy latency modules are installed."
            )
        return TeensyLatency(com, baudrate=baudrate)

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
            self.teensy = self._create_teensy(com, baudrate)
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


def get_available_processors() -> Dict[str, Dict[str, Any]]:
    return {
        "dlc_inference_w_pd": {
            "class": dlc_inference_w_pd,
            "name": getattr(dlc_inference_w_pd, "PROCESSOR_NAME", "dlc_inference_w_pd"),
            "description": getattr(dlc_inference_w_pd, "PROCESSOR_DESCRIPTION", ""),
            "params": getattr(dlc_inference_w_pd, "PROCESSOR_PARAMS", {}),
        }
    }

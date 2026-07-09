"""Sync photodiode processor that reuses the shared DLC/socket behavior."""

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict
import logging

import numpy as np
from dlclivegui.processors import PROCESSOR_REGISTRY, register_processor  # type: ignore[import-not-found]

try:
    from dlc_utils.dlc_processor_socket_pd import dlc_inference_w_pd
except ModuleNotFoundError:
    _local_path = Path(__file__).with_name("dlc_processor_socket_pd.py")
    _local_name = "dlclivegui_plugins.local_dlc_processor_socket_pd"
    _spec = importlib.util.spec_from_file_location(_local_name, _local_path)
    if _spec is None or _spec.loader is None:
        raise ImportError(f"Could not import dlc_inference_w_pd from {_local_path}")
    _module = sys.modules.get(_local_name)
    if _module is None:
        _module = importlib.util.module_from_spec(_spec)
        sys.modules[_local_name] = _module
        _spec.loader.exec_module(_module)
    dlc_inference_w_pd = _module.dlc_inference_w_pd

import_issues = None
try:
    from latency_tests.Teensy_latency.TeensyLatencySync import TeensyLatencySync
except ModuleNotFoundError as e:
    TeensyLatencySync = None
    import_issues = e

PROCESSOR_REGISTRY.pop("dlc_inference_w_pd_sync", None)
logger = logging.getLogger(__name__)

@register_processor
class dlc_inference_w_pd_sync(dlc_inference_w_pd):
    PROCESSOR_NAME = "SocketProcessorWithPDSync"
    HEAD_CONF_THRESHOLD = 0.01
    PROCESSOR_DESCRIPTION = "Photodiode processor with Teensy sync timing capture."
    PROCESSOR_BUILD_IN_WORKER = True # legacy initialization ensures compatibility with old dlclivegui processors
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
        logger.info(
            f"Listener status: {self.listener._listener._socket.getsockname()} with authkey: {self.authkey}"
        )

    def _create_teensy(self, com, baudrate):
        if TeensyLatencySync is None:
            raise ImportError(
                "TeensyLatencySync dependency is unavailable. Ensure mouse_task is on PYTHONPATH "
                "and Teensy latency modules are installed."
            ) from import_issues
        return TeensyLatencySync(com, baudrate=baudrate)

    def save_latency_data(self) -> Dict[str, Any]:
        save_dict = super().save_latency_data()

        if self.use_teensy == 1:
            save_dict["ttl_read"] = np.array(getattr(self.teensy, "input_data_ttl", []))
            save_dict["teensy_time"] = np.array(
                getattr(self.teensy, "input_data_teensy_time", [])
            )

        return save_dict


def get_available_processors() -> Dict[str, Dict[str, Any]]:
    return {
        "dlc_inference_w_pd_sync": {
            "class": dlc_inference_w_pd_sync,
            "name": getattr(dlc_inference_w_pd_sync, "PROCESSOR_NAME", "dlc_inference_w_pd_sync"),
            "description": getattr(dlc_inference_w_pd_sync, "PROCESSOR_DESCRIPTION", ""),
            "params": getattr(dlc_inference_w_pd_sync, "PROCESSOR_PARAMS", {}),
        }
    }

"""Sync photodiode processor that reuses the shared DLC/socket behavior."""

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, Optional
import logging
import warnings
import pickle

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
        self.save_path: Optional[Path] = None
        try:
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
        except Exception as e:
            self.stop(save=False)
            raise RuntimeError(
                f"Failed to initialize dlc_inference_w_pd_sync: {e}."
            ) from e

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
    
    def save(self, file: Optional[str] = None) -> int:
        """Save processor data.

        If `file` is not provided, uses `self.save_path`.
        """
        target = file

        if target is None:
            target = getattr(self, "save_path", None)

        if target is None:
            warnings.warn("Processor save skipped: no file or save_path was provided.")
            return 0

        try:
            target = Path(target)
            target.parent.mkdir(parents=True, exist_ok=True)

            save_dict = self.save_latency_data()

            with target.open("wb") as f:
                pickle.dump(save_dict, f)

            print(f"Processor data saved to: {target}")
            return 1

        except Exception as e:
            warnings.warn(f"Proc file was not saved, an exception occurred: {e}")
            return -1
        
    def stop(self, save: bool = False, file: str | None = None) -> None:
        """Cleanly stop processor resources.

        Args:
            save:
                If True, call self.save(file) before closing resources.
            file:
                Output path for processor data. If None, no save is attempted unless
                the parent class has a meaningful default filename.
        """

        # 1. Optional save first, while all buffers/objects still exist.
        if save:
            try:
                if file is not None:
                    self.save(file)
                else:
                    # Avoid saving to an unknown location unless explicitly requested.
                    print("Processor stop(save=True) called without file; skipping save.")
            except Exception as exc:
                print(f"Processor save during stop failed: {exc}")

        # 2. Close Teensy serial if available.
        try:
            teensy = getattr(self, "teensy", None)
            if teensy is not None:
                close_serial = getattr(teensy, "close_serial", None)
                if callable(close_serial):
                    close_serial()
                else:
                    close = getattr(teensy, "close", None)
                    if callable(close):
                        close()
        except Exception as exc:
            print(f"Failed to close Teensy cleanly: {exc}")
        finally:
            try:
                self.teensy = None
            except Exception:
                pass

        # 3. Close accepted socket connection.
        try:
            conn = getattr(self, "conn", None)
            if conn is not None:
                conn.close()
        except Exception as exc:
            print(f"Failed to close processor socket connection: {exc}")
        finally:
            try:
                self.conn = None
            except Exception:
                pass

        # 4. Close listener on port 6000.
        try:
            listener = getattr(self, "listener", None)
            if listener is not None:
                listener.close()
        except Exception as exc:
            print(f"Failed to close processor listener: {exc}")
        finally:
            try:
                self.listener = None
            except Exception:
                pass


    def close(self) -> None:
        """Alias for generic cleanup."""
        self.stop(save=False)


def get_available_processors() -> Dict[str, Dict[str, Any]]:
    return {
        "dlc_inference_w_pd_sync": {
            "class": dlc_inference_w_pd_sync,
            "name": getattr(dlc_inference_w_pd_sync, "PROCESSOR_NAME", "dlc_inference_w_pd_sync"),
            "description": getattr(dlc_inference_w_pd_sync, "PROCESSOR_DESCRIPTION", ""),
            "params": getattr(dlc_inference_w_pd_sync, "PROCESSOR_PARAMS", {}),
        }
    }

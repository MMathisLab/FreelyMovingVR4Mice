import pickle
import time
import importlib.util
import sys
import warnings
from collections import deque
from math import acos, atan2, copysign, degrees, sqrt
from multiprocessing.connection import Listener
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from numpy.typing import NDArray
from dlclivegui.processors import PROCESSOR_REGISTRY, register_processor  # type: ignore[import-not-found]

try:
    from dlc_utils.processor_with_signal import ProcessorWithSignal
except ModuleNotFoundError:
    _local_path = Path(__file__).with_name("processor_with_signal.py")
    _local_name = "dlclivegui_plugins.local_processor_with_signal"
    _spec = importlib.util.spec_from_file_location(_local_name, _local_path)
    if _spec is None or _spec.loader is None:
        raise ImportError(f"Could not import ProcessorWithSignal from {_local_path}")
    _module = sys.modules.get(_local_name)
    if _module is None:
        _module = importlib.util.module_from_spec(_spec)
        sys.modules[_local_name] = _module
        _spec.loader.exec_module(_module)
    ProcessorWithSignal = _module.ProcessorWithSignal

PROCESSOR_REGISTRY.pop("MyProcessor_socket", None)


@register_processor
class MyProcessor_socket(ProcessorWithSignal):
    HEAD_CONF_THRESHOLD = 0.6
    PROCESSOR_NAME = "SocketProcessor"
    PROCESSOR_DESCRIPTION = "Sends DLC-derived kinematics over a local socket."
    PROCESSOR_PARAMS = {
        "bind": {
            "type": "tuple",
            "default": ("127.0.0.1", 6000),
            "description": "Server bind address as (host, port).",
        },
        "authkey": {
            "type": "bytes",
            "default": b"secret password",
            "description": "Authentication key for socket clients.",
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
    }

    def __init__(
        self,
        bind: tuple[str, int] = ("127.0.0.1", 6000),
        authkey: bytes = b"secret password",
        signal_delay: float = 10,
        signal_type: str = "pulse_geo",
        freq: float = 5,
    ) -> None:
        super().__init__(signal_delay=signal_delay, signal_type=signal_type, freq=freq)

        self.address = bind
        self.authkey = authkey
        self.listener = Listener(self.address, authkey=self.authkey)
        self.conn = None
        try:
            self.listener._listener._socket.settimeout(0.0)
        except Exception:
            pass

        self.center_x = deque()
        self.center_y = deque()
        self.heading_direction = deque()
        self.head_angle = deque()
        self.time_stamp = deque()
        self.signal = deque()
        self.step = deque()
        self.frame_time = deque()
        self.pose_time = deque()
        self.curr_step = 0  # frame counter
        self.previous = np.array([0, 0])

    def _ensure_connection(self) -> None:
        if self.conn is not None:
            return
        try:
            self.conn = self.listener.accept()
            print("Connection accepted from", self.listener.last_accepted)
        except Exception:
            self.conn = None

    def process(self, pose: NDArray[np.float64], **kwargs: Any) -> NDArray[np.float64]:

        xy = pose[:, :2]
        conf = pose[:, 2]

        head_xy = xy[[0, 1, 2, 3, 4, 5, 6, 26], :]
        head_conf = conf[[0, 1, 2, 3, 4, 5, 6, 26]]

        if np.mean(head_conf) < self.HEAD_CONF_THRESHOLD:
            center = self.previous
        else:
            center = np.average(head_xy, axis=0, weights=head_conf)

        body_axis = xy[7] - xy[13]  # tail_base -> neck
        body_axis /= sqrt(np.sum(body_axis**2))

        head_axis = xy[0] - xy[7]  # neck -> nose
        head_axis /= sqrt(np.sum(head_axis**2))

        cross = body_axis[0] * head_axis[1] - head_axis[0] * body_axis[1]
        sign = copysign(1, cross)  # Positive when looking left

        try:
            head_angle = acos(body_axis @ head_axis) * sign
        except ValueError:
            head_angle = 0

        self.curr_time = time.time()
        self.curr_signal = self.get_signal(curr_time=self.curr_time)

        self.curr_step = self.curr_step + 1

        heading = atan2(body_axis[1], body_axis[0])
        heading = degrees(heading)
        vals = *center, heading % (360), head_angle, self.curr_signal

        self.center_x.append(vals[0])
        self.center_y.append(vals[1])
        self.heading_direction.append(vals[2])
        self.head_angle.append(vals[3])
        self.time_stamp.append(self.curr_time)
        self.step.append(self.curr_step)
        self.signal.append(self.curr_signal)
        self.frame_time.append(kwargs.get("frame_time", self.curr_time))

        self._ensure_connection()
        if self.conn is not None:
            try:
                self.conn.send([time.time(), vals[0], vals[1], vals[2], vals[3], vals[4]])
            except Exception:
                self.conn = None
        self.previous = center
        return pose

    def save(self, file: Optional[str] = None) -> int:
        save_code = 0
        if file:
            try:
                save_dict = self.save_latency_data()

                pickle.dump(
                    save_dict,
                    open(file, "wb"),
                )
                save_code = 1
            except Exception as e:
                warnings.warn(f"Proc file was not saved, an exception occurred: {e}")

                save_code = -1
        return save_code

    def save_latency_data(self) -> Dict[str, Any]:
        save_dict = dict()
        save_dict["start_time"] = np.array(self.start_time)
        save_dict["frame_time"] = np.array(self.frame_time)
        save_dict["time_stamp"] = np.array(self.time_stamp)
        save_dict["step"] = np.array(self.step)
        save_dict["signal"] = np.array(self.signal)
        save_dict["x_pos"] = np.array(self.center_x)
        save_dict["y_pos"] = np.array(self.center_y)
        save_dict["heading_direction"] = np.array(self.heading_direction)
        save_dict["head_angle"] = np.array(self.head_angle)

        return save_dict


def get_available_processors() -> Dict[str, Dict[str, Any]]:
    return {
        "MyProcessor_socket": {
            "class": MyProcessor_socket,
            "name": getattr(MyProcessor_socket, "PROCESSOR_NAME", "MyProcessor_socket"),
            "description": getattr(MyProcessor_socket, "PROCESSOR_DESCRIPTION", ""),
            "params": getattr(MyProcessor_socket, "PROCESSOR_PARAMS", {}),
        }
    }

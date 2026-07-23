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
    """DLC-live processor that streams mouse kinematics to a local socket client.

    Each `process()` call converts a DLC pose into center position, heading,
    and head angle, appends it to in-memory buffers (drained on `save()`),
    and pushes the same values to a connected client over a
    `multiprocessing.connection.Listener`. Also owns the generic
    resource-cleanup contract (`stop`/`close`) used by all socket-based
    processors in this module, since it's the class that owns the listener
    and connection.
    """

    HEAD_CONF_THRESHOLD = 0.6

    # Legacy initialization ensures compatibility with old DLCLiveGUI processors:
    # sockets / serial / side-effect-heavy resources are created inside DLCLiveWorker.
    PROCESSOR_BUILD_IN_WORKER = True

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

    @staticmethod
    def _select_single_pose(pose: Any) -> np.ndarray:
        """Return one pose with shape (K, 3).

        Accepts:
            (K, 3): already a single pose.
            (N, K, 3): one or more detections.

        For multiple detections, selects the detection with the highest
        mean keypoint likelihood.
        """
        poses = np.asarray(pose)

        if poses.ndim == 2:
            if poses.shape[1] != 3:
                raise ValueError(f"Expected pose shape (K, 3), got {poses.shape}")
            return poses

        if poses.ndim == 3:
            if poses.shape[0] == 0 or poses.shape[2] != 3:
                raise ValueError(f"Expected pose shape (N, K, 3), got {poses.shape}")

            if poses.shape[0] == 1:
                return poses[0]

            scores = np.nanmean(poses[..., 2], axis=1)

            if not np.isfinite(scores).any():
                warnings.warn(
                    "No detection has a finite confidence score; selecting detection 0"
                )
                return poses[0]

            index = int(np.nanargmax(scores))
            return poses[index]

        raise ValueError(f"Expected pose shape (K, 3) or (N, K, 3), got {poses.shape}")

    def process(self, pose: NDArray[np.float64], **kwargs: Any) -> NDArray[np.float64]:
        """Derive kinematics from a DLC pose and stream them to the socket client.

        Computes head-weighted center position (falling back to the previous
        center when head-keypoint confidence is low), body/head heading, and
        head angle; appends each to the processor's buffers and sends them
        over `self.conn` if a client is connected. Returns the single-animal
        pose used for the computation (see `_select_single_pose`).
        """
        pose = self._select_single_pose(pose)  # IMPORTANT: not multi-animal friendly

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
                self.conn.send(
                    [time.time(), vals[0], vals[1], vals[2], vals[3], vals[4]]
                )
            except Exception:
                self.conn = None
        self.previous = center
        return pose

    def save(self, file: Optional[str] = None) -> int:
        """Pickle `save_latency_data()` to `file`.

        Returns 1 on success, -1 on error, 0 if no file given.
        """
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
        """Collect buffered kinematics/timing arrays for saving. Subclasses extend this dict."""
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

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def stop(self, save: bool = False, file: Optional[str] = None) -> None:
        """Cleanly stop processor resources.

        Subclasses with extra resources to release (e.g. a serial device)
        should override `_close_extra_resources` rather than `stop` itself,
        so they don't need to re-implement the save/socket/listener sequence.
        """
        if save:
            try:
                self.save(file)
            except Exception:
                warnings.warn("Processor save during stop failed")

        self._close_extra_resources()
        self._close_socket_connection()
        self._close_listener()

    def close(self) -> None:
        """Alias for generic cleanup."""
        self.stop(save=False)

    def _close_extra_resources(self) -> None:
        """Hook for subclasses to close resources beyond the socket/listener. No-op by default."""

    def _close_socket_connection(self) -> None:
        try:
            conn = getattr(self, "conn", None)
            if conn is not None:
                conn.close()
        except Exception:
            warnings.warn("Failed to close processor socket connection")
        finally:
            self.conn = None

    def _close_listener(self) -> None:
        try:
            listener = getattr(self, "listener", None)
            if listener is not None:
                listener.close()
        except Exception:
            warnings.warn("Failed to close processor listener")
        finally:
            self.listener = None


def get_available_processors() -> Dict[str, Dict[str, Any]]:
    return {
        "MyProcessor_socket": {
            "class": MyProcessor_socket,
            "name": getattr(MyProcessor_socket, "PROCESSOR_NAME", "MyProcessor_socket"),
            "description": getattr(MyProcessor_socket, "PROCESSOR_DESCRIPTION", ""),
            "params": getattr(MyProcessor_socket, "PROCESSOR_PARAMS", {}),
        }
    }

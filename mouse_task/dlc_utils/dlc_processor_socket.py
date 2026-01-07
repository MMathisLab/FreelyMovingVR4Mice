import pickle
import time
import warnings
from collections import deque
from math import acos, atan2, copysign, degrees, pi, sqrt
from multiprocessing.connection import Listener
from typing import Any, Dict, Optional

import numpy as np
from numpy.typing import NDArray

from mouse_task.dlc_utils.processor_with_signal import ProcessorWithSignal


class MyProcessor_socket(ProcessorWithSignal):
    def __init__(
        self, signal_delay: float = 10, signal_type: str = "pulse_geo", freq: float = 5
    ) -> None:
        super().__init__(signal_delay=signal_delay, signal_type=signal_type, freq=freq)

        self.address = ("localhost", 6000)  # family is deduced to be 'AF_INET'
        self.listener = Listener(self.address, authkey=b"secret password")
        self.conn = self.listener.accept()
        print("Connection accepted from", self.listener.last_accepted)

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

    def process(self, pose: NDArray[np.float64], **kwargs: Any) -> NDArray[np.float64]:
        xy = pose[:, :2]
        conf = pose[:, 2]
        head_xy = xy[[0, 1, 2, 3, 4, 5, 6, 26], :]
        head_conf = conf[[0, 1, 2, 3, 4, 5, 6, 26]]

        if np.mean(head_conf) < 0.6:
            center = self.previous
        else:
            center = np.average(head_xy, axis=0, weights=head_conf)

        body_axis /= sqrt(np.sum((xy[7] - xy[13]) ** 2))  # tail_base -> neck
        head_axis /= sqrt(np.sum((xy[0] - xy[7]) ** 2))  # neck -> nose
        cross = body_axis[0] * head_axis[1] - head_axis[0] * body_axis[1]
        sign = copysign(1, cross)  # Positive when looking left
        try:
            head_angle = acos(body_axis @ head_axis) * sign
        except ValueError:
            head_angle = 0

        self.curr_time = time.time()  # wall-clock timestamp for this frame
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
        self.frame_time.append(kwargs["frame_time"])

        self.conn.send([time.time(), vals[0], vals[1], vals[2], vals[3], vals[4]])
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

    def save_latency_data(self) -> Dict[str, NDArray[np.float64]]:
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

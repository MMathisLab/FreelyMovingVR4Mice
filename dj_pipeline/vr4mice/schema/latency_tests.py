from pathlib import Path
from typing import List, Optional

import datajoint as dj
import pandas as pd
import numpy as np
from vr4mice.schema import vr4mice
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema
from vr4mice.analysis.latency_testing import get_signals, find_rising_edges, get_latency

schema_name = "latency_tests"
schema = get_schema(schema_name, locals())
logger = Logger.get_logger()


@schema
class SignalPhotodiodeAligned(dj.Computed):
    definition = """
    -> vr4mice.SignalPhotodiode
    ---
    time_stamp: float # time stamp of the interpolated of the generated and photodiode signal   
    send_time: float # time stamp of the interpolated of the generated signal
    frame_to_socket_time: float # time difference between the frame and the signal send time
    signal_read: float # value of the generated signal
    photodiode_time: float # time stamp of the interpolated of the photodiode signal
    photodiode_read: float # value of the photodiode signal
    photodiode_raw_scaled: float # scaled value of the photodiode signal
    filtered_photodiode_scaled: float # filtered value of the photodiode signal
    threshold: float # threshold value of the photodiode signal
    """

    def make(self, key):
        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        try:
            data = (vr4mice.SignalPhotodiode() & key).fetch1(as_dict=True)
            data = dict(get_signals(data))
            self.insert1(**key, **data)

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )


class AllLatencies(dj.Computed):
    definition = """
    -> SignalPhotodiodeAligned
    ---
    frame_time: float # time stamp of the interpolated of the generated frame time
    time_diff: float # time differences between the generated signal and the photodiode signal's rising edge
    photodiode_time: float # time stamp of the interpolated of the photodiode signal's rising edge
    frame_to_socket: float # time difference between the frame and the signal send time
    """

    def make(self, key):
        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        try:
            df = pd.DataFrame((SignalPhotodiodeAligned() & key).fetch1(as_dict=True))
            rising_edges_a = find_rising_edges(df.time_stamp, df.signal_read)
            rising_edges_photodiode = find_rising_edges(
                df.time_stamp, df.photodiode_read
            )
            latencies = get_latency(rising_edges_a, rising_edges_photodiode)

            raw_data = (vr4mice.SignalPhotodiode() & key).fetch1(
                "generated_frame_time", "generated_send_time", as_dict=True
            )
            latencies["frame_to_socket"] = np.mean(
                raw_data["generated_send_time"][100:]
                - raw_data["generated_frame_time"][100:]
            )
            data = dict(latencies)
            self.insert1(**key, **data)

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)
            return None

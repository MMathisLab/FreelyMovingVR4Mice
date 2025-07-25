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
class SignalsPhotodiodeAligned(dj.Computed):
    definition = """
    -> vr4mice.SignalsPhotodiode
    ---
    time_stamp: longblob    # time stamp of the interpolated of the generated and photodiode signal   
    send_time: longblob     # time stamp of the interpolated of the generated signal
    frame_to_socket_time: longblob # time difference between the frame and the signal send time
    signal_read: longblob       # value of the generated signal
    photodiode_read: longblob   # value of the photodiode signal
    photodiode_raw_scaled: longblob         # scaled value of the photodiode signal
    filtered_photodiode_scaled: longblob    # filtered value of the photodiode signal
    threshold: longblob                     # threshold value of the photodiode signal
    """

    def make(self, key):
        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        try:
            logger.info(f"{key['dataset']}")
            data = (vr4mice.SignalsPhotodiode() & key).fetch(as_dict=True)[0]
            data = get_signals(data).to_dict()

            if len(np.unique(np.array(list(data["photodiode_read"].values())))) != 2:
                raise ValueError(
                    f"Photodiode signal in {key['dataset']} is not binary, check that the photodiode was recording."
                )
            
            data = {**key, **data}
            self.insert1(data, allow_direct_insert=True)
        except Exception as err:
            dataset = key["dataset"]

            logger.warning(
                f"{self.__class__.__name__} population failed: key: {dataset[key]}, {err}"
            )
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )


@schema
class AllLatencies(dj.Computed):
    definition = """
    -> SignalsPhotodiodeAligned
    ---
    frame_time: longblob    # time stamp of the interpolated of the generated frame time
    time_diff: longblob     # time differences between the generated signal and the photodiode signal's rising edge
    photodiode_time: longblob   # time stamp of the interpolated of the photodiode signal's rising edge
    frame_to_socket: longblob   # time difference between the frame and the signal send time
    """

    def make(self, key):
        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        try:
            logger.info(f"{key['dataset']}")
            photodiode_df = pd.DataFrame((SignalsPhotodiodeAligned() & key).fetch(
                "time_stamp",  "signal_read", "photodiode_read", as_dict=True
            )[0])

            rising_edges_a = find_rising_edges(photodiode_df.time_stamp, photodiode_df.signal_read)
            rising_edges_photodiode = find_rising_edges(
                photodiode_df.time_stamp, photodiode_df.photodiode_read
            )
            latencies = get_latency(rising_edges_a, rising_edges_photodiode)

            raw_data = (vr4mice.SignalsPhotodiode() & key).fetch(
                "generated_frame_time", "generated_send_time", as_dict=True
            )[0]
            latencies["frame_to_socket"] = np.mean(
                raw_data["generated_send_time"][100:]
                - raw_data["generated_frame_time"][100:]
            )
            data = latencies.to_dict()
            self.insert1({**key, **data}, allow_direct_insert=True)

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            
            logger.warning(f"Can't populate {self.__class__.__name__}, key: {dataset}. Error: {err}.")
            return None

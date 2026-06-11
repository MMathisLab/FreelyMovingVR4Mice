"""Latency testing schema for photodiode and frame timing analysis."""

import datajoint as dj
import numpy as np
import pandas as pd

from vr4mice.analysis.latency_testing import find_rising_edges, get_latency, get_signals
from vr4mice.schema import vr4mice
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

schema_name = "latency_tests"
schema = get_schema(schema_name, locals())
logger = Logger.get_logger()


@schema
class SignalsPhotodiodeAligned(dj.Computed):
    """
    SignalsPhotodiodeAligned definition table:
    stores interpolated and aligned photodiode and generated sync signals
    """

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
        """Align photodiode and generated signals for latency analysis."""
        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
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
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)

            return None

    @classmethod
    def get_photodiode_df(cls, key: dict) -> pd.DataFrame:
        data = (cls & key).fetch1()

        return pd.DataFrame(
            {"send_time": data["send_time"], "signal_read": data["signal_read"]}
        )

    @classmethod
    def get_dlc_df(cls, key: dict) -> pd.DataFrame:
        data = (cls & key).fetch1()

        return pd.DataFrame(
            {
                "time_stamp": data["time_stamp"],
                "photodiode_read": data["photodiode_read"],
                "photodiode_raw_scaled": data["photodiode_raw_scaled"],
                "filtered_photodiode_scaled": data["filtered_photodiode_scaled"],
            }
        )


@schema
class AllLatencies(dj.Computed):
    """
    AllLatencies definition table:
    stores per-session latency between generated and photodiode signal edges
    """

    definition = """
    -> SignalsPhotodiodeAligned
    ---
    frame_time: longblob    # time stamp of the interpolated of the generated frame time
    time_diff: longblob     # time differences between the generated signal and the photodiode signal's rising edge
    photodiode_time: longblob   # time stamp of the interpolated of the photodiode signal's rising edge
    frame_to_socket: longblob   # time difference between the frame and the signal send time
    """

    def make(self, key):
        """Compute per-session latency distributions and summary stats."""
        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            logger.info(f"{key['dataset']}")
            photodiode_df = pd.DataFrame(
                (SignalsPhotodiodeAligned() & key).fetch(
                    "time_stamp", "signal_read", "photodiode_read", as_dict=True
                )[0]
            )

            rising_edges_a = find_rising_edges(
                photodiode_df.time_stamp, photodiode_df.signal_read
            )
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
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)

            return None

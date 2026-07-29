"""DLC-related schema tables for keypoints and derived kinematics."""

from typing import List, Optional

import datajoint as dj
import numpy as np
import pandas as pd

from vr4mice.analysis.barcodes import (
    BarcodeDecoderConfig,
    decode_teensy_barcodes,
    has_teensy_ttl_data,
    normalize_ttl_read,
)
from vr4mice.schema import vr4mice
import vr4mice.analysis.dlc_helpers as dlc_helpers
from vr4mice.utils import logger, schema_config

schema_name = "dlc"
schema = schema_config.get_schema(schema_name, locals())

logger = logger.Logger.get_logger()


def _complete_dlc_key(key: dict) -> dict:
    """Return the full `vr4mice.DLC` primary key for `key` when needed."""
    if "camera" not in key or "doe" not in key:
        matches = (vr4mice.DLC() & key).fetch(*vr4mice.DLC().primary_key, as_dict=True)
        if len(matches) == 0:
            raise KeyError(
                f"No vr4mice.DLC entry found to complete key from partial key: {key}"
            )
        return matches[0]
    return key


@schema
class DLCProcessor(dj.Imported):
    """
    DLCProcessor definition table:
    imports processed DLC outputs from the PROC npy file
    """

    definition = """
    -> vr4mice.DLC
    ---
    start_time=NULL: <blob>
    frame_time=NULL: <blob>
    time_stamp=NULL: <blob>
    step=NULL: <blob>
    signal=NULL: <blob>
    photodiode_read=NULL: <blob>
    photodiode_time=NULL: <blob>
    x_pos: <blob>
    y_pos: <blob>
    heading_direction: <blob>
    head_angle: <blob>
    teensy_time=NULL: <blob>  # ms timestamp from the Teensy microcontroller of the analog/digital read
    ttl_read=NULL: <blob>  # Barcode TTL signal for Ephys sync
    has_ttl=false: bool  # True if the DLC session has a TTL signal for Ephys sync
    """

    def make(self, key):
        """Load DLC processed outputs into the DLCProcessor table."""

        if self & key:
            logger.debug(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            fpath = (vr4mice.DLC & key).fetch1("proc_filepath")
            proc_data = np.load(fpath, allow_pickle=True)
            if isinstance(proc_data, np.ndarray) and proc_data.ndim == 0:
                proc_data = proc_data.item()

            key = _complete_dlc_key(key)  # TODO: add allow_direct_insert in arg

            # PROC files may include metadata (e.g. signal_type) not stored in DLCProcessor
            table_attrs = set(self.heading.names) - set(self.primary_key)
            data = {
                **key,
                **{attr: proc_data[attr] for attr in table_attrs if attr in proc_data},
            }
            if "ttl_read" in data and data["ttl_read"] is not None:
                data["ttl_read"] = normalize_ttl_read(data["ttl_read"])
            data["has_ttl"] = has_teensy_ttl_data(proc_data)
            self.insert1(data, allow_direct_insert=True)
            logger.info(f"{self.__class__.__name__} populated for {key}.")

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)

            return None


@schema
class TeensyBarcodes(dj.Computed):
    """Barcode events decoded from the TTL signal sampled by the Teensy."""

    definition = """
    -> DLCProcessor
    ---
    decoder_parameters: <blob>  # Parameters supplied to the decoder
    extraction_status: enum('success','no_events')  # Extraction outcome
    event_count: int32  # Number of decoded barcode events
    quality_summary: <blob>  # Decoder diagnostics and signal-quality values
    """

    key_source = DLCProcessor & {"has_ttl": True}
    decoder_config = BarcodeDecoderConfig()

    class Event(dj.Part):
        definition = """
        -> master
        barcode_index: int32  # Zero-based event order in the stream
        ---
        barcode_value: int64  # Integer payload encoded by the barcode
        onset_sample: int64  # Teensy millisecond timestamp at event onset
        onset_time: float64  # Corresponding photodiode_time acquisition timestamp
        onset_time_relative: float64  # onset_time relative to the session start_time
        """

    def make(self, key):
        """Decode and store all barcodes in one Teensy TTL recording."""
        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            teensy_time, ttl_read, photodiode_time, start_time = (
                DLCProcessor & key
            ).fetch1(
                "teensy_time",
                "ttl_read",
                "photodiode_time",
                "start_time",
            )
            result = decode_teensy_barcodes(
                teensy_time,
                ttl_read,
                photodiode_time,
                start_time,
                config=self.decoder_config,
            )
            status = "success" if result.events else "no_events"
            self.insert1(
                {
                    **key,
                    "decoder_parameters": self.decoder_config.to_dict(),
                    "extraction_status": status,
                    "event_count": len(result.events),
                    "quality_summary": result.quality,
                }
            )
            if result.events:
                self.Event.insert(
                    [
                        {
                            **key,
                            "barcode_index": event.index,
                            "barcode_value": event.value,
                            "onset_sample": event.onset_sample,
                            "onset_time": event.onset_time,
                            "onset_time_relative": event.onset_time_relative,
                        }
                        for event in result.events
                    ]
                )
            logger.info(
                "%s extracted %d Teensy barcodes for %s",
                self.__class__.__name__,
                len(result.events),
                key,
            )

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            logger.warning(
                "Can't populate %s, key: %s. Error: %s.",
                self.__class__.__name__,
                key,
                err,
            )
            return None


@schema
class DLCKptsDf(dj.Computed):
    """All available raw DLC keypoints with likelihood."""

    definition = """
    -> vr4mice.DLC
    ---
    data: <blob>
    headers : <blob>
    scorer=NULL: varchar(256)
    """

    def make(self, key: dict):
        """Store raw DLC keypoints and metadata for a dataset."""

        if self & key:
            logger.debug(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        logger.info(f"Populating {self.__class__.__name__} for {key}.")
        try:
            h5_path = (vr4mice.DLC & key).fetch1("keypoints_filepath")
            data = dlc_helpers.h5_to_dj(h5_path)
            key = _complete_dlc_key(key)
            data = {**key, **data}
            self.insert1(data, allow_direct_insert=True)
            logger.info(f"{self.__class__.__name__} populated for {key}.")

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)

            return None

    def get_data(
        self, key: dict, columns: Optional[List[str]] = None
    ) -> Optional[pd.DataFrame]:
        try:
            if self & key:
                if columns:
                    raise NotImplementedError()
                else:
                    data = (self & key).fetch1()
            return dlc_helpers.dj_to_df(data["data"], data["headers"], data["scorer"])

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None


@schema
class SyncDLCKptsDf(dj.Computed):
    """Filtered and game-synchronized DLC keypoints."""

    definition = """
    -> DLCKptsDf
    ---
    data: <blob>
    headers : <blob>
    scorer=NULL: varchar(256)
    """

    def make(self, key: dict):
        """Synchronize DLC keypoints to game time and store results."""

        if self & key:
            logger.debug(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        logger.info(f"Populating {self.__class__.__name__} for {key}.")
        try:
            sync_kpts = dlc_helpers.sync_keypoint_table(
                dataset_key=key, keypoint_cuttoff=0.6, filter_window_length=10
            )
            data = dlc_helpers.df_to_dj(sync_kpts)

            key = _complete_dlc_key(key)  # TODO: add allow_direct_insert in arg

            data = {**key, **data}
            self.insert1(data, allow_direct_insert=True)
            logger.info(f"{self.__class__.__name__} populated for {key}.")

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)

            return None

    def get_data(
        self, key: dict, columns: Optional[List[str]] = None
    ) -> Optional[pd.DataFrame]:
        try:
            if self & key:
                if columns:
                    raise NotImplementedError()
                else:
                    data = (self & key).fetch1()
            return dlc_helpers.dj_to_df(data["data"], data["headers"], data["scorer"])

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None


@schema
class OfflineKinematics(dj.Computed):
    """Stores the mouse body kinematics that are computed offline.
    This table pulls data from the synchronized and interpolated DLC keypoint table
    and recomputes various kinematic variables.
    """

    definition = """
    -> SyncDLCKptsDf
    ---
    head_center_x: <blob> # the center of the mouse head in x at each frame
    head_center_y: <blob> # the center of the mouse head in y at each frame
    heading_dir: <blob> # the direction of the mouses body (tail base to neck) relative to the main screen 
    head_angle: <blob> # the angle of the head relative to heading_dir
    pose_time: <blob> # the time that the pose was inferred
    step_time: <blob> # the time of the frame in game time
    step: <blob> # the nearest game step to the dlc frame
    """

    def make(self, key: dict):
        """Compute offline kinematic features from synchronized keypoints."""

        if self & key:
            logger.debug(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        logger.info(f"Populating {self.__class__.__name__} for {key}.")

        try:

            sync_keypoints = SyncDLCKptsDf().get_data(key)
            if sync_keypoints is False or sync_keypoints is None:
                logger.info(
                    f"The SyncDLCKptsDf for could not be returned {self.__class__.__name__} could not be populated for {key}"
                )
                return None

            data = dlc_helpers.get_offline_dlc_variables(sync_keypoints)
            data = data.to_dict(orient="list")
            key = _complete_dlc_key(key)  # TODO: add allow_direct_insert in arg

            data = {**key, **data}
            self.insert1(data, allow_direct_insert=True)
            logger.info(f"{self.__class__.__name__} populated for {key}.")

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)
            return None

    def get_data(
        self, key: dict, columns: Optional[List[str]] = None
    ) -> Optional[pd.DataFrame]:
        try:
            if self & key:
                data = (self & key).fetch1()
                if columns:
                    data = {k: v for k, v in data.items() if k in columns}
                return pd.DataFrame(data)
            else:
                return False

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}: {err}")
            return None

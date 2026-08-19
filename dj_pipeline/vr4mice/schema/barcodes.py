"""Schema for barcodes recorded through the Teensy synchronization channel."""

from pathlib import Path

import datajoint as dj
import numpy as np

from vr4mice.analysis.barcodes import (
    BarcodeDecoderConfig,
    decode_teensy_barcodes,
    has_teensy_ttl_data,
    normalize_ttl_read,
)
import vr4mice.analysis.dlc_helpers as dlc_helpers
from vr4mice.schema import base_analysis, dlc, vr4mice
from vr4mice.utils import logger, schema_config

schema_name = "barcodes"
schema = schema_config.get_schema(schema_name, locals())

logger = logger.Logger.get_logger()


@schema
class TeensyTTL(dj.Imported):
    """Raw Teensy barcode channel imported from a DLC PROC file.

    Threshold semantics:
    a session is eligible when its resolved Batch (via DatasetBatch) has
    ``has_neural_data=True``. Batch membership boundaries come from
    ``Batch.resolve`` (latest ``start_date <= doe``), so boundary dates are
    inclusive for the newer batch.
    """

    definition = """
    -> vr4mice.DLC
    ---
    teensy_time=NULL: <blob>  # Teensy millisecond timestamp for each TTL sample
    ttl_read=NULL: <blob>  # Barcode TTL samples stored as integer zero or one
    has_ttl=0: bool  # True when aligned, non-empty Teensy TTL arrays are available
    """

    # Gate by resolved batch membership (not direct date filtering here):
    # DLC session -> DatasetBatch -> Batch(has_neural_data=True).
    # Per-session mixed TTL availability is still handled by has_ttl.
    key_source = (
        vr4mice.DLC.proj()
        * vr4mice.DatasetBatch.proj("batch_name")
        * (vr4mice.Batch & {"has_neural_data": True}).proj("batch_name")
    )

    def make(self, key):
        """Load the raw Teensy TTL arrays from one DLC PROC file."""
        if self & key:
            logger.debug(
                "%s already contains key %s; skipping duplicate",
                self.__class__.__name__,
                key,
            )
            return

        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        proc_filepath_raw = None
        proc_path = None
        try:
            proc_filepath_raw = (vr4mice.DLC & key).fetch1("proc_filepath")
            proc_path = Path(str(proc_filepath_raw)).expanduser()

            if not proc_path.is_file():
                logger.warning(
                    "Transient missing file for %s, key: %s. DLC PROC file not found for TeensyTTL. Looked for: '%s' (raw proc_filepath=%r)",
                    self.__class__.__name__,
                    key,
                    proc_path,
                    proc_filepath_raw,
                )
                return

            proc_data = np.load(proc_path, allow_pickle=True)
            if isinstance(proc_data, np.ndarray) and proc_data.ndim == 0:
                proc_data = proc_data.item()

            data = {
                **key,
                "has_ttl": has_teensy_ttl_data(proc_data),
            }
            if "teensy_time" in proc_data:
                data["teensy_time"] = proc_data["teensy_time"]
            if "ttl_read" in proc_data and proc_data["ttl_read"] is not None:
                data["ttl_read"] = normalize_ttl_read(proc_data["ttl_read"])

            self.insert1(data, allow_direct_insert=True)
            logger.info("%s populated for %s", self.__class__.__name__, key)

        except Exception as err:
            dataset = key.get("dataset", "unknown")
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            logger.warning(
                "Can't populate %s, key: %s. proc_filepath=%r, looked_for=%s. Recorded in FailedSession. Error: %s.",
                self.__class__.__name__,
                key,
                proc_filepath_raw,
                proc_path,
                err,
            )
            return None


@schema
class TeensyBarcodes(dj.Computed):
    """Barcode events decoded from the TTL signal sampled by the Teensy."""

    definition = """
    -> TeensyTTL
    -> dlc.DLCProcessor
    -> base_analysis.DataFrame
    ---
    decoder_parameters: <blob>  # Parameters supplied to the decoder
    extraction_status: enum('success','no_events')  # Extraction outcome
    event_count: int32  # Number of decoded barcode events
    quality_summary: <blob>  # Decoder diagnostics and signal-quality values
    """

    key_source = (
        (TeensyTTL & {"has_ttl": True}).proj()
        * dlc.DLCProcessor.proj()
        * base_analysis.DataFrame.proj()
    )
    decoder_config = BarcodeDecoderConfig()

    class Event(dj.Part):
        definition = """
        -> master
        barcode_index: int32  # Zero-based event order in the stream
        ---
        barcode_value: int64  # Integer payload encoded by the barcode
        onset_sample: int64  # Teensy millisecond timestamp at event onset
        onset_time: float64  # Corresponding photodiode_time acquisition timestamp
        onset_time_unity=NULL: float64  # Nearest base_analysis.DataFrame step_time (NULL when outside step_time range)
        """

    def make(self, key):
        """Decode and store all barcodes in one Teensy TTL recording."""
        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            teensy_time, ttl_read = (TeensyTTL & key).fetch1(
                "teensy_time",
                "ttl_read",
            )
            photodiode_time = (dlc.DLCProcessor & key).fetch1(
                "photodiode_time",
            )
            result = decode_teensy_barcodes(
                teensy_time,
                ttl_read,
                photodiode_time,
                config=self.decoder_config,
            )
            game_start_time = float(
                np.asarray(
                    (vr4mice.State & {"dataset": key["dataset"]}).fetch1("start_time")
                ).item()
            )
            step_time = (base_analysis.DataFrame & key).fetch1("step_time")
            event_step_times = dlc_helpers.align_timestamps_to_step_time(
                [event.onset_time - game_start_time for event in result.events],
                step_time,
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
                            "onset_time_unity": (
                                float(onset_step_time)
                                if np.isfinite(onset_step_time)
                                else None
                            ),
                        }
                        for event, onset_step_time in zip(
                            result.events, event_step_times, strict=True
                        )
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

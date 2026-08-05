"""Alignment of VR (behavior) time to Neuropixels (NP) native time via shared barcodes.

Not every VR ``Dataset`` has a corresponding NP recording; ``BarcodeSync.key_source``
intersects with the NP-side linkage tables so ``populate()`` simply never calls
``make()`` for behavior-only sessions, instead of raising.
"""

import pickle

import datajoint as dj
import numpy as np

try:
    from np_pipeline.schemas import acquisition, barcodes as np_barcodes, session_link
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, "/np_pipeline")
    from np_pipeline.schemas import acquisition, barcodes as np_barcodes, session_link

from vr4mice.analysis.np_sync import DEFAULT_SKIP_FIRST_N_BARCODES, align_barcodes
from vr4mice.schema import base
from vr4mice.schema import barcodes as vr_barcodes
from vr4mice.schema import vr4mice
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

schema_name = "np_sync"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()


@schema
class BarcodeSync(dj.Computed):
    """Linear fit + interpolator mapping VR Unity/game time to NP OneBox DAQ time."""

    definition = """
    -> base.Base
    -> session_link.RecordingSessionLink
    -> acquisition.OneBoxDaq
    ---
    skip_first_n_barcodes: smallint unsigned  # leading VR barcode events excluded from the fit
    slope: float  # Slope of the linear fit mapping VR time to NP time
    intercept: float  # Intercept of the linear fit mapping VR time to NP time
    r2: float  # R-squared value of the linear fit
    interpol_func: <blob>  # pickled scipy.interpolate.interp1d, VR time -> NP time
    barcode_overlap: float  # Fraction of NP barcodes also found on the VR side
    """

    key_source = (
        base.Base * session_link.RecordingSessionLink * acquisition.OneBoxDaq
        & (vr_barcodes.TeensyBarcodes & 'extraction_status = "success"')
        & (np_barcodes.OneBoxBarcodeExtraction & 'extraction_status = "success"')
    )

    skip_first_n_barcodes = DEFAULT_SKIP_FIRST_N_BARCODES

    def make(self, key):
        """Fit a VR-time-to-NP-time alignment from shared barcode events."""
        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            vr_values, vr_times = (vr_barcodes.TeensyBarcodes.Event & key).fetch(
                "barcode_value", "onset_time_unity", order_by="barcode_index"
            )
            np_values, np_times = (np_barcodes.OneBoxBarcodeExtraction.Event & key).fetch(
                "barcode_value", "onset_time", order_by="barcode_index"
            )

            fit = align_barcodes(
                vr_times,
                vr_values,
                np_times,
                np_values,
                skip_first_n_barcodes=self.skip_first_n_barcodes,
            )

            self.insert1(
                {
                    **key,
                    "skip_first_n_barcodes": self.skip_first_n_barcodes,
                    "slope": fit.slope,
                    "intercept": fit.intercept,
                    "r2": fit.r2,
                    "interpol_func": pickle.dumps(fit.interpol_func),
                    "barcode_overlap": len(fit.shared_barcodes) / len(np_values),
                }
            )
            logger.info(
                "%s aligned %d shared barcodes for %s",
                self.__class__.__name__,
                len(fit.shared_barcodes),
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

    @classmethod
    def align_timepoints(cls, sess_key, timepoints: list):
        """Convert VR times to NP times using interpolation (accounts for clock drift)."""
        interpol_func = pickle.loads((cls & sess_key).fetch1("interpol_func"))
        timepoints = np.array(timepoints, dtype=np.float64)
        return [float(tx) if not np.isnan(tx) else None for tx in interpol_func(timepoints)]

    @classmethod
    def align_timepoints_lin(cls, sess_key, timepoints: list):
        """Convert VR times to NP times using the linear fit only."""
        slope, intercept = (cls & sess_key).fetch1("slope", "intercept")
        return [tx * slope + intercept if tx is not None else None for tx in timepoints]

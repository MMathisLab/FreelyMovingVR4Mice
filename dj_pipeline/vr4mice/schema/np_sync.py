"""Alignment of VR (behavior) time to Neuropixels (NP) native time via shared barcodes.

Not every VR ``Dataset`` has a corresponding NP recording; ``BarcodeSync.key_source``
intersects with the NP-side linkage tables so ``populate()`` simply never calls
``make()`` for behavior-only sessions, instead of raising.

Cross-repo foreign keys: ``BarcodeSync`` references ``np_pipeline`` tables
directly via ``-> ``. This requires ``vr4mice`` and ``np_pipeline`` to share one
MySQL server (``DJ_HOST``) and one process-global ``dj.conn()`` — both already
satisfied by this repo's connection setup. `np_sync` is imported as its own
isolated step in ``run.py``/``cron_scenario.py``, so a missing ``np_pipeline``
only skips NP sync, not the rest of the pipeline.
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
    """Linear fit + interpolator mapping VR Unity/game time to NP OneBox DAQ time.

    One row per (dataset, recording, OneBox DAQ stream) triple that has a linked NP
    recording and successfully decoded barcodes on both sides. Populated only for
    those keys — see ``key_source`` — so ``populate()`` is a no-op, not an error, for
    VR-only sessions with no matching neural recording.

    Downstream code should not fetch ``slope``/``intercept``/``interpol_func``
    directly; use ``align_timepoints``/``align_timepoints_lin`` instead.
    """

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
        """Fit and insert one VR-time-to-NP-time alignment.

        Fetches decoded barcode events for one dataset/recording/DAQ key from both
        `vr_barcodes.TeensyBarcodes.Event` (VR side) and
        `np_barcodes.OneBoxBarcodeExtraction.Event` (NP side), fits the alignment via
        `vr4mice.analysis.np_sync.align_barcodes`, and inserts the resulting fit
        parameters and pickled interpolator. On failure, records the error in
        `vr4mice.FailedSession` and logs a warning instead of raising, matching the
        error-handling convention used by `barcodes.TeensyTTL`/`TeensyBarcodes`.
        """
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
    def align_timepoints(cls, key, timepoints: list):
        """Convert a list of VR times to NP times via the fitted interpolator.

        Preferred over `align_timepoints_lin` for most uses: the interpolator is fit
        only within the range spanned by the shared barcode events, so it captures
        any small clock drift between the VR and NP streams rather than assuming a
        perfectly constant offset/rate.

        Args:
            key: A restriction identifying exactly one `BarcodeSync` row (e.g. a
                dataset/recording/DAQ key).
            timepoints: VR-side times (`onset_time_unity`-style values) to convert.
                `None` entries pass through as `None`; DataJoint-`NULL`/`NaN`-producing
                extrapolation misses become `None` as well.

        Returns:
            A list of NP-side times (or `None`), same length and order as `timepoints`.
        """
        interpol_func = pickle.loads((cls & key).fetch1("interpol_func"))
        timepoints = np.array(timepoints, dtype=np.float64)
        return [float(tx) if not np.isnan(tx) else None for tx in interpol_func(timepoints)]

    @classmethod
    def align_timepoints_lin(cls, key, timepoints: list):
        """Convert a list of VR times to NP times via the fitted line only (`y = slope*x + intercept`).

        Faster than `align_timepoints` and fine for a single global rate/offset, but
        ignores any local clock drift the interpolator would otherwise correct for.

        Args:
            key: A restriction identifying exactly one `BarcodeSync` row.
            timepoints: VR-side times to convert; `None` entries pass through as `None`.

        Returns:
            A list of NP-side times (or `None`), same length and order as `timepoints`.
        """
        slope, intercept = (cls & key).fetch1("slope", "intercept")
        return [tx * slope + intercept if tx is not None else None for tx in timepoints]

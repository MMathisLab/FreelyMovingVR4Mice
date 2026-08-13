"""Alignment of VR (behavior) time to Neuropixels (NP) native time via shared barcodes.

Not every VR ``Dataset`` has a corresponding NP recording. ``BarcodeSync.key_source``
contains only strict VR/NP matches (via ``base.Base`` +
``session_link.RecordingSessionLink`` + successful NP probe barcode extraction),
so VR-only datasets are excluded from this table and are not visited by
``populate()``.

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
    from np_pipeline.schemas import barcodes as np_barcodes, session_link
except ModuleNotFoundError:
    import sys

    # Keep np_pipeline imports resilient when process CWD is not /app.
    sys.path.insert(0, "/app/np_pipeline/src")
    sys.path.insert(0, "/app/np_pipeline")
    from np_pipeline.schemas import barcodes as np_barcodes, session_link

from vr4mice.analysis.np_sync import DEFAULT_SKIP_FIRST_N_BARCODES, align_barcodes
from vr4mice.schema import base
from vr4mice.schema import barcodes as vr_barcodes
from vr4mice.schema import vr4mice
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

schema_name = "np_sync"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()


def _candidate_relation():
    """Rows where one VR dataset has at least one NP probe with successful barcodes."""
    vr = (
        base.Base
        * (vr_barcodes.TeensyBarcodes & 'extraction_status = "success"').proj()
    )
    npx = (
        session_link.RecordingSessionLink
        * (np_barcodes.ProbeBarcodeExtraction & 'extraction_status = "success"').proj()
    )

    return vr * npx


@schema
class BarcodeSync(dj.Computed):
    """Linear fit + interpolator mapping VR Unity/game time to NP probe time.

    One row per related VR/NP barcode pair with successful extraction on both sides.
    The table is explicitly keyed by ``TeensyBarcodes`` (VR side) and
    ``ProbeBarcodeExtraction`` (NP side). ``key_source`` enforces strict matching
    through ``base.Base`` + ``RecordingSessionLink`` + ``recording_id`` so
    ``populate()`` only visits related rows; sessions with no strict NP match are
    invisible to this table.

    Downstream code should not fetch ``slope``/``intercept``/``interpol_func``
    directly; use ``align_timepoints``/``align_timepoints_lin`` instead.
    """

    definition = """
    -> vr_barcodes.TeensyBarcodes
    -> np_barcodes.ProbeBarcodeExtraction
    ---
    skip_first_n_barcodes: int32  # leading VR barcode events excluded from the fit
    slope: float64  # Slope of the linear fit mapping VR time to NP time
    intercept: float64  # Intercept of the linear fit mapping VR time to NP time
    r2: float64  # R-squared value of the linear fit
    interpol_func: <blob>  # pickled scipy.interpolate.interp1d, VR time -> NP time
    barcode_overlap: float64  # Fraction of NP barcodes also found on the VR side
    """

    @property
    def key_source(self):
        source = _candidate_relation()
        unexpected = sorted(set(source.heading.primary_key) - set(self.primary_key))
        if unexpected:
            raise dj.DataJointError(
                f"key_source primary key has attributes BarcodeSync lacks: {unexpected}"
            )
        return source

    skip_first_n_barcodes = DEFAULT_SKIP_FIRST_N_BARCODES
    min_shared_barcodes = 20
    min_barcode_overlap = 0.90

    def make(self, key):
        """Fit and insert one VR-time-to-NP-time alignment.

        Fetches decoded barcode events for one dataset/recording/probe key from both
        `vr_barcodes.TeensyBarcodes.Event` (VR side) and
        `np_barcodes.ProbeBarcodeExtraction.Event` (NP side), fits the alignment via
        `vr4mice.analysis.np_sync.align_barcodes`, and inserts the resulting fit
        parameters and pickled interpolator. On failure, records the error in
        `vr4mice.FailedSession` and logs a warning instead of raising, matching the
        error-handling convention used by `barcodes.TeensyTTL`/`TeensyBarcodes`.
        """
        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            candidate_rows = (_candidate_relation() & key).to_dicts()
            if not candidate_rows:
                reason = "No NP candidate matched key fields"
                vr4mice.FailedSession().add_entry(
                    f"{key['dataset']}", f"{self.__class__.__name__}", reason
                )
                logger.warning(
                    "%s %s for dataset %s",
                    self.__class__.__name__,
                    reason,
                    key["dataset"],
                )
                return
            if len(candidate_rows) > 1:
                reason = "Ambiguous NP candidates matched key fields"
                vr4mice.FailedSession().add_entry(
                    f"{key['dataset']}", f"{self.__class__.__name__}", reason
                )
                logger.warning(
                    "%s %s for dataset %s",
                    self.__class__.__name__,
                    reason,
                    key["dataset"],
                )
                return

            vr_values, vr_times = (vr_barcodes.TeensyBarcodes.Event & key).to_arrays(
                "barcode_value", "onset_time_unity", order_by="barcode_index"
            )
            np_values, np_times = (
                np_barcodes.ProbeBarcodeExtraction.Event & key
            ).to_arrays("barcode_value", "onset_time", order_by="barcode_index")

            if len(np_values) == 0:
                reason = (
                    "No NP barcode events found for key at populate time "
                    "(events may have been removed after key_source selection)"
                )
                vr4mice.FailedSession().add_entry(
                    f"{key['dataset']}", f"{self.__class__.__name__}", reason
                )
                logger.warning(
                    "%s %s. key: %s",
                    self.__class__.__name__,
                    reason,
                    key,
                )
                return

            fit = align_barcodes(
                vr_times,
                vr_values,
                np_times,
                np_values,
                skip_first_n_barcodes=self.skip_first_n_barcodes,
            )

            # Measure overlap on full streams (independent of fit-time skipping)
            # so DEFAULT_SKIP_FIRST_N_BARCODES does not bias this quality metric.
            full_shared_barcodes = np.intersect1d(vr_values, np_values)
            np_unique_barcodes = np.unique(np_values)
            barcode_overlap = len(full_shared_barcodes) / len(np_unique_barcodes)

            if len(fit.shared_barcodes) < self.min_shared_barcodes:
                reason = (
                    "Insufficient shared barcodes for reliable NP-VR alignment "
                    f"(shared={len(fit.shared_barcodes)}, "
                    f"min_required={self.min_shared_barcodes})"
                )
                vr4mice.FailedSession().add_entry(
                    f"{key['dataset']}", f"{self.__class__.__name__}", reason
                )
                logger.warning(
                    "%s %s for dataset %s",
                    self.__class__.__name__,
                    reason,
                    key["dataset"],
                )
                return

            if barcode_overlap <= self.min_barcode_overlap:
                reason = (
                    "Insufficient NP-VR barcode overlap for reliable alignment "
                    f"(overlap={barcode_overlap:.4f}, "
                    f"min_required>{self.min_barcode_overlap:.4f})"
                )
                vr4mice.FailedSession().add_entry(
                    f"{key['dataset']}", f"{self.__class__.__name__}", reason
                )
                logger.warning(
                    "%s %s for dataset %s",
                    self.__class__.__name__,
                    reason,
                    key["dataset"],
                )
                return

            self.insert1(
                {
                    **key,
                    "skip_first_n_barcodes": self.skip_first_n_barcodes,
                    "slope": fit.slope,
                    "intercept": fit.intercept,
                    "r2": fit.r2,
                    "interpol_func": pickle.dumps(fit.interpol_func),
                    "barcode_overlap": barcode_overlap,
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
        timepoints = np.array(
            [np.nan if tx is None else tx for tx in timepoints], dtype=np.float64
        )
        return [
            float(tx) if not np.isnan(tx) else None for tx in interpol_func(timepoints)
        ]

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

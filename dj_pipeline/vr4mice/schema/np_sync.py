"""Alignment of VR (behavior) time to Neuropixels (NP) native time via shared barcodes.

Not every VR ``Dataset`` has a corresponding NP recording. ``BarcodeSync.key_source``
includes datasets with successful VR barcode extraction, while strict NP linkage
matching is performed inside ``make()`` via ``base.Base`` +
``session_link.RecordingSessionLink`` + successful NP probe barcode extraction.
Datasets with no strict NP match are recorded in ``vr4mice.FailedSession`` and
skipped cleanly.

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


def _dataset_identity(dataset: str):
    """Return (mouse_name, day_iso, attempt) parsed from dataset name."""
    parts = dataset.split("_")
    if len(parts) < 3:
        return None
    try:
        return parts[0], parts[1], int(parts[2])
    except ValueError:
        return None


def _candidate_sort_key(row, identity):
    """Sort candidates by identity match first, then NP barcode event count."""
    event_count = int(row["np_event_count"])
    if identity is None:
        return (
            -event_count,
            str(row.get("recording_id", "")),
            str(row.get("probe_serial_number", "")),
        )

    expected_mouse, expected_day, expected_attempt = identity
    mouse_miss = 0 if row.get("mouse_name") == expected_mouse else 1
    day = row.get("day")
    day_iso = day.isoformat() if hasattr(day, "isoformat") else str(day)
    day_miss = 0 if day_iso == expected_day else 1
    attempt_miss = 0 if row.get("attempt") == expected_attempt else 1
    return (
        mouse_miss,
        day_miss,
        attempt_miss,
        -event_count,
        str(row.get("recording_id", "")),
        str(row.get("probe_serial_number", "")),
    )


def _np_module_options():
    """Return available NP schema-module triplets, preferring imported modules."""
    options = [(acquisition, np_barcodes, session_link)]
    legacy = (
        dj.VirtualModule("np_acquisition_legacy", "acquisition"),
        dj.VirtualModule("np_barcodes_legacy", "barcodes"),
        dj.VirtualModule("np_session_link_legacy", "session_link"),
    )
    imported_lineage = acquisition.RecordingProbe.heading.attributes[
        "recording_id"
    ].lineage
    legacy_lineage = legacy[0].RecordingProbe.heading.attributes["recording_id"].lineage
    if legacy_lineage != imported_lineage:
        options.append(legacy)
    return options


def _candidate_relation_for_modules(acq_mod, np_barcodes_mod, session_link_mod):
    """Rows where one VR dataset has at least one NP probe with successful barcodes."""
    np_success = (
        np_barcodes_mod.ProbeBarcodeExtraction & 'extraction_status = "success"'
    ).proj(
        "recording_id",
        "probe_serial_number",
        np_event_count="event_count",
    )
    return (
        base.Base
        * acq_mod.RecordingProbe
        * session_link_mod.RecordingSessionLink
        * np_success
        & (vr_barcodes.TeensyBarcodes & 'extraction_status = "success"')
    )


@schema
class BarcodeSync(dj.Computed):
    """Linear fit + interpolator mapping VR Unity/game time to NP probe time.

    One row per VR dataset that has at least one linked NP recording/probe with
    successful barcodes on both sides. ``key_source`` enumerates VR datasets with
    successful VR barcode extraction; strict NP-side eligibility is resolved in
    ``make()``. Sessions with no strict NP match are recorded to
    ``vr4mice.FailedSession`` and skipped.

    Downstream code should not fetch ``slope``/``intercept``/``interpol_func``
    directly; use ``align_timepoints``/``align_timepoints_lin`` instead.
    """

    definition = """
    -> base.Base
    ---
    recording_id: varchar(255)  # Linked NP recording selected for this dataset
    probe_serial_number: varchar(64)  # Selected NP probe used for alignment
    skip_first_n_barcodes: int32  # leading VR barcode events excluded from the fit
    slope: float64  # Slope of the linear fit mapping VR time to NP time
    intercept: float64  # Intercept of the linear fit mapping VR time to NP time
    r2: float64  # R-squared value of the linear fit
    interpol_func: <blob>  # pickled scipy.interpolate.interp1d, VR time -> NP time
    barcode_overlap: float64  # Fraction of NP barcodes also found on the VR side
    """

    @property
    def key_source(self):
        return dj.U("dataset") & (
            base.Base * (vr_barcodes.TeensyBarcodes & 'extraction_status = "success"')
        )

    skip_first_n_barcodes = DEFAULT_SKIP_FIRST_N_BARCODES

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
            selected = None
            selected_modules = None
            identity = _dataset_identity(key["dataset"])
            for modules in _np_module_options():
                acq_mod, np_barcodes_mod, session_link_mod = modules
                candidates = (
                    _candidate_relation_for_modules(
                        acq_mod, np_barcodes_mod, session_link_mod
                    )
                    & key
                )
                if len(candidates) == 0:
                    continue
                selected_modules = modules
                candidate_rows = candidates.fetch(as_dict=True)
                candidate_rows = sorted(
                    candidate_rows,
                    key=lambda row: _candidate_sort_key(row, identity),
                )
                selected = candidate_rows[0]
                break

            if selected is None or selected_modules is None:
                reason = "No eligible NP barcode source for dataset from strict session-link matching"
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

            _, np_barcodes_mod, _ = selected_modules
            np_key = {
                "recording_id": selected["recording_id"],
                "probe_serial_number": selected["probe_serial_number"],
            }
            vr_values, vr_times = (vr_barcodes.TeensyBarcodes.Event & key).fetch(
                "barcode_value", "onset_time_unity", order_by="barcode_index"
            )
            np_values, np_times = (
                np_barcodes_mod.ProbeBarcodeExtraction.Event & np_key
            ).fetch("barcode_value", "onset_time", order_by="barcode_index")

            fit = align_barcodes(
                vr_times,
                vr_values,
                np_times,
                np_values,
                skip_first_n_barcodes=self.skip_first_n_barcodes,
            )

            insert_row = {}
            for name in self.heading.names:
                if name in key:
                    insert_row[name] = key[name]
                elif name in selected:
                    insert_row[name] = selected[name]

            self.insert1(
                {
                    **insert_row,
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

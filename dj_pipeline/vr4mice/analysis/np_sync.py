"""Fit a VR-time-to-NP-time alignment from barcode values shared by both streams."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.interpolate
import scipy.stats


def _same_timebin(a: float, b: float) -> bool:
    """Return True when two onset_time_unity values belong to the same bin."""
    return bool(np.isclose(a, b, rtol=0.0, atol=1e-12, equal_nan=True))


def _leading_repetitive_run_length(vr_times: np.ndarray) -> int:
    """Length of the first consecutive equal-time run."""
    if vr_times.size == 0:
        return 0

    run_length = 1
    while run_length < vr_times.size and _same_timebin(
        vr_times[run_length - 1], vr_times[run_length]
    ):
        run_length += 1
    return run_length


def _trailing_repetitive_run_length(vr_times: np.ndarray) -> int:
    """Length of the last consecutive equal-time run."""
    if vr_times.size == 0:
        return 0

    run_length = 1
    idx = vr_times.size - 1
    while idx > 0 and _same_timebin(vr_times[idx], vr_times[idx - 1]):
        run_length += 1
        idx -= 1
    return run_length


def _trim_repetitive_boundary_timebins(
    vr_times: np.ndarray, vr_values: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Drop consecutive repetitive onset_time_unity runs at start and end.

    When the first/last VR barcode events all map to the same Unity timebin,
    those boundary runs are unreliable for cross-clock fitting and are removed.
    """
    leading_run = _leading_repetitive_run_length(vr_times)
    if leading_run >= 2:
        vr_times = vr_times[leading_run:]
        vr_values = vr_values[leading_run:]

    trailing_run = _trailing_repetitive_run_length(vr_times)
    if trailing_run >= 2:
        vr_times = vr_times[:-trailing_run]
        vr_values = vr_values[:-trailing_run]

    return vr_times, vr_values


@dataclass(frozen=True)
class BarcodeAlignmentFit:
    """Linear fit + interpolator mapping VR time to NP time."""

    slope: float
    intercept: float
    r2: float
    interpol_func: scipy.interpolate.interp1d
    shared_barcodes: np.ndarray


def align_barcodes(
    vr_times: np.ndarray,
    vr_values: np.ndarray,
    np_times: np.ndarray,
    np_values: np.ndarray,
    skip_first_n_barcodes: int = 0,
) -> BarcodeAlignmentFit:
    """Fit VR time -> NP time from barcode values shared between both streams.

    Alignment approach (intersect1d + linregress + interp1d) ported from
    cross_analysis_schemas/schemas/vr_np_sync.py::BarcodeSync.align_barcodes in
    https://github.com/AdaptiveMotorControlLab/auxPipelines-DataJoint_Mathis,
    adapted for this repo's VR (vr4mice) / NP (np_pipeline) schemas.

    Args:
        vr_times: VR-side barcode onset times, ordered by event index (chronological).
        vr_values: VR-side barcode integer payloads, same order as `vr_times`.
        np_times: NP-side barcode onset times, ordered by event index.
        np_values: NP-side barcode integer payloads, same order as `np_times`.
        skip_first_n_barcodes: legacy number of leading VR events to exclude
            before matching. Defaults to 0; boundary repetitive-bin trimming is
            applied first and should usually be sufficient.
    """
    vr_times = np.asarray(vr_times)
    vr_values = np.asarray(vr_values)
    np_times = np.asarray(np_times)
    np_values = np.asarray(np_values)

    if vr_times.shape != vr_values.shape:
        raise ValueError("vr_times and vr_values must have matching shapes")
    if np_times.shape != np_values.shape:
        raise ValueError("np_times and np_values must have matching shapes")

    vr_times, vr_values = _trim_repetitive_boundary_timebins(vr_times, vr_values)

    if skip_first_n_barcodes:
        vr_times = vr_times[skip_first_n_barcodes:]
        vr_values = vr_values[skip_first_n_barcodes:]

    shared_barcodes, vr_index, np_index = np.intersect1d(
        vr_values, np_values, return_indices=True
    )

    vr_shared_times = np.asarray(vr_times)[vr_index]
    np_shared_times = np.asarray(np_times)[np_index]

    if vr_shared_times.size < 2:
        raise ValueError(
            "Need at least 2 shared barcode events after boundary trimming "
            "to fit VR-to-NP alignment"
        )

    linreg = scipy.stats.linregress(vr_shared_times, np_shared_times)
    interpol_func = scipy.interpolate.interp1d(
        vr_shared_times,
        np_shared_times,
        bounds_error=False,
        fill_value="extrapolate",
    )

    return BarcodeAlignmentFit(
        slope=linreg.slope,
        intercept=linreg.intercept,
        r2=linreg.rvalue**2,
        interpol_func=interpol_func,
        shared_barcodes=shared_barcodes,
    )

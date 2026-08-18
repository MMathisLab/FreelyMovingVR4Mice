"""Fit a VR-time-to-NP-time alignment from barcode values shared by both streams."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.interpolate
import scipy.stats

MIN_TIE_POINTS = 3
OUTLIER_SIGMA = 5.0
OUTLIER_FLOOR_MS = 30.0
OUTLIER_MAX_FRACTION = 0.05


def _boundary_repetitive_run_lengths(vr_times: np.ndarray) -> tuple[int, int]:
    """Return leading/trailing consecutive equal-time run lengths.

    Direct `!=` is intentional here: onset_time_unity values at repeated
    boundaries are copied from the same step_time array element and are
    therefore expected to be bit-identical.
    """
    if vr_times.size == 0:
        return 0, 0

    change_points = np.flatnonzero(vr_times[1:] != vr_times[:-1]) + 1
    run_starts = np.concatenate(([0], change_points))
    run_ends = np.concatenate((change_points, [vr_times.size]))
    run_lengths = run_ends - run_starts
    return int(run_lengths[0]), int(run_lengths[-1])


def _trim_repetitive_boundary_timebins(
    vr_times: np.ndarray, vr_values: np.ndarray
) -> tuple[np.ndarray, np.ndarray, int, int]:
    """Drop consecutive repetitive onset_time_unity runs at start and end.

    When the first/last VR barcode events all map to the same Unity timebin,
    those boundary runs are unreliable for cross-clock fitting and are removed.
    """
    leading_run, trailing_run = _boundary_repetitive_run_lengths(vr_times)
    n_trimmed_leading = leading_run if leading_run >= 2 else 0
    if leading_run >= 2:
        vr_times = vr_times[leading_run:]
        vr_values = vr_values[leading_run:]

    _, trailing_run = _boundary_repetitive_run_lengths(vr_times)
    n_trimmed_trailing = trailing_run if trailing_run >= 2 else 0
    if trailing_run >= 2:
        vr_times = vr_times[:-trailing_run]
        vr_values = vr_values[:-trailing_run]

    return vr_times, vr_values, n_trimmed_leading, n_trimmed_trailing


@dataclass(frozen=True)
class BarcodeAlignmentFit:
    """Linear fit + interpolator mapping VR time to NP time, with diagnostics."""

    slope: float
    intercept: float
    r2: float
    rmse_ms: float
    max_abs_residual_ms: float
    interpol_func: scipy.interpolate.interp1d
    shared_barcodes: np.ndarray
    n_trimmed_leading: int
    n_trimmed_trailing: int
    n_rejected_outliers: int


def _inlier_mask(
    vr_shared_times: np.ndarray,
    np_shared_times: np.ndarray,
    *,
    sigma: float = OUTLIER_SIGMA,
    floor_ms: float = OUTLIER_FLOOR_MS,
    max_fraction: float = OUTLIER_MAX_FRACTION,
    max_iterations: int = 10,
) -> np.ndarray:
    """Iteratively reject tie points whose residual is a robust outlier.

    Residuals are centered on their median before scoring. A least-squares line
    through a contaminated set can sit between clean and displaced points; an
    uncentered rule then risks dropping all points instead of the offenders.
    """
    keep = np.ones(vr_shared_times.shape, dtype=bool)
    for _ in range(max_iterations):
        fit = scipy.stats.linregress(vr_shared_times[keep], np_shared_times[keep])
        residual_ms = (
            np_shared_times - (fit.slope * vr_shared_times + fit.intercept)
        ) * 1000.0
        center = float(np.median(residual_ms[keep]))
        scale = 1.4826 * float(np.median(np.abs(residual_ms[keep] - center)))
        threshold = max(float(floor_ms), float(sigma) * scale)
        updated = np.abs(residual_ms - center) <= threshold
        n_dropped = int((~updated).sum())
        if (
            n_dropped > max_fraction * vr_shared_times.size
            or int(updated.sum()) < MIN_TIE_POINTS
        ):
            raise ValueError(
                f"{n_dropped} of {vr_shared_times.size} barcode tie points are residual "
                f"outliers (more than {max_fraction:.0%}); the VR/NP relation is not "
                "simply linear for this session and no fit through it is trustworthy"
            )
        if np.array_equal(updated, keep):
            break
        keep = updated

    return keep


def align_barcodes(
    vr_times: np.ndarray,
    vr_values: np.ndarray,
    np_times: np.ndarray,
    np_values: np.ndarray,
    *,
    reject_outliers: bool = True,
) -> BarcodeAlignmentFit:
    """Fit VR time -> NP time from barcode values shared between both streams.

    Alignment approach (intersect1d + linregress + interp1d) ported from
    cross_analysis_schemas/schemas/vr_np_sync.py::BarcodeSync.align_barcodes in
    https://github.com/AdaptiveMotorControlLab/auxPipelines-DataJoint_Mathis,
    adapted for this repo's VR (vr4mice) / NP (np_pipeline) schemas.

    Before fitting, the function validates 1D, finite, non-empty inputs,
    trims repetitive boundary Unity timebins on the VR stream, intersects
    shared barcode values, and requires at least ``MIN_TIE_POINTS`` shared
    tie points.

    Args:
        vr_times: VR-side barcode onset times, ordered by event index (chronological).
        vr_values: VR-side barcode integer payloads, same order as `vr_times`.
        np_times: NP-side barcode onset times, ordered by event index.
        np_values: NP-side barcode integer payloads, same order as `np_times`.
        reject_outliers: When True, iteratively remove robust residual outliers
            before fitting, using a median-centered MAD criterion with a
            floor-based threshold in milliseconds.

    Raises:
        ValueError: If shapes differ, inputs are not 1D, either stream is empty,
            non-finite timepoints are present, or fewer than
            ``MIN_TIE_POINTS`` shared tie points remain after preprocessing.
    """
    vr_times = np.asarray(vr_times)
    vr_values = np.asarray(vr_values)
    np_times = np.asarray(np_times)
    np_values = np.asarray(np_values)

    if vr_times.shape != vr_values.shape:
        raise ValueError("vr_times and vr_values must have matching shapes")
    if np_times.shape != np_values.shape:
        raise ValueError("np_times and np_values must have matching shapes")
    if vr_times.ndim != 1 or np_times.ndim != 1:
        raise ValueError("barcode streams must be one-dimensional")
    if vr_times.size == 0 or np_times.size == 0:
        raise ValueError("both barcode streams must be non-empty")
    for name, times in (("onset_time_unity", vr_times), ("NP onset_time", np_times)):
        n_bad = int((~np.isfinite(times)).sum())
        if n_bad:
            raise ValueError(
                f"{n_bad} of {times.size} {name} values are NaN or infinite and "
                "cannot be used as tie points"
            )
    if np.unique(vr_times).size == 1:
        raise ValueError(
            "All barcode events have the same onset_time_unity; "
            "cannot fit VR-to-NP alignment"
        )

    vr_times, vr_values, n_trimmed_leading, n_trimmed_trailing = (
        _trim_repetitive_boundary_timebins(vr_times, vr_values)
    )

    shared_barcodes, vr_index, np_index = np.intersect1d(
        vr_values, np_values, return_indices=True
    )

    vr_shared_times = np.asarray(vr_times)[vr_index]
    np_shared_times = np.asarray(np_times)[np_index]

    if vr_shared_times.size < MIN_TIE_POINTS:
        raise ValueError(
            f"Need at least {MIN_TIE_POINTS} shared barcode events after boundary trimming "
            "to fit VR-to-NP alignment"
        )

    n_rejected_outliers = 0
    if reject_outliers:
        keep = _inlier_mask(vr_shared_times, np_shared_times)
        n_rejected_outliers = int((~keep).sum())
        vr_shared_times = vr_shared_times[keep]
        np_shared_times = np_shared_times[keep]
        shared_barcodes = shared_barcodes[keep]

    linreg = scipy.stats.linregress(vr_shared_times, np_shared_times)
    predicted_np = linreg.slope * vr_shared_times + linreg.intercept
    residual_ms = (np_shared_times - predicted_np) * 1000.0
    rmse_ms = float(np.sqrt(np.mean(np.square(residual_ms))))
    max_abs_residual_ms = float(np.max(np.abs(residual_ms)))
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
        rmse_ms=rmse_ms,
        max_abs_residual_ms=max_abs_residual_ms,
        interpol_func=interpol_func,
        shared_barcodes=shared_barcodes,
        n_trimmed_leading=n_trimmed_leading,
        n_trimmed_trailing=n_trimmed_trailing,
        n_rejected_outliers=n_rejected_outliers,
    )

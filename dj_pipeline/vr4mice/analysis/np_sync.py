"""Fit a VR-time-to-NP-time alignment from barcode values shared by both streams."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.interpolate
import scipy.stats

# Number of leading (chronologically earliest) VR barcode events excluded from the
# regression fit by default. DLC-live starts receiving data slightly after the
# Unity/game stream does, which is why downstream analysis already drops
# `trial == 1` as a DLC-live initialization trial (see vr4mice/analysis/analysis.py).
# Barcodes in that same early window can carry an unreliable onset_time_unity,
# biasing the fit if used as tie points, so we drop the earliest few by default.
DEFAULT_SKIP_FIRST_N_BARCODES = 10


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

    Args:
        vr_times: VR-side barcode onset times, ordered by event index (chronological).
        vr_values: VR-side barcode integer payloads, same order as `vr_times`.
        np_times: NP-side barcode onset times, ordered by event index.
        np_values: NP-side barcode integer payloads, same order as `np_times`.
        skip_first_n_barcodes: number of leading (earliest) VR events to exclude
            before matching, to avoid the DLC-live startup-lag window.
    """
    if skip_first_n_barcodes:
        vr_times = vr_times[skip_first_n_barcodes:]
        vr_values = vr_values[skip_first_n_barcodes:]

    shared_barcodes, vr_index, np_index = np.intersect1d(
        vr_values, np_values, return_indices=True
    )

    vr_shared_times = np.asarray(vr_times)[vr_index]
    np_shared_times = np.asarray(np_times)[np_index]

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

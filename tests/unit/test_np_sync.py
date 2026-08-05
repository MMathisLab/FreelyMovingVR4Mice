"""Unit tests for the VR-to-NP barcode alignment fit."""

import numpy as np
import pytest

from np_sync import align_barcodes


def _linear_barcode_streams(*, n=20, slope=2.0, intercept=100.0, skip_vr=0, skip_np=0):
    """Two barcode streams sharing all-but-`skip_*` values, related by a known linear fit."""
    values = np.arange(n)
    vr_times = np.arange(n, dtype=np.float64)
    np_times = slope * vr_times + intercept

    vr_values = values[skip_vr:] if skip_vr else values
    vr_times = vr_times[skip_vr:] if skip_vr else vr_times
    np_values = values[skip_np:] if skip_np else values
    np_times = np_times[skip_np:] if skip_np else np_times

    return vr_times, vr_values, np_times, np_values


def test_align_barcodes_recovers_known_linear_fit():
    vr_times, vr_values, np_times, np_values = _linear_barcode_streams(
        slope=2.0, intercept=100.0
    )

    fit = align_barcodes(vr_times, vr_values, np_times, np_values)

    assert fit.slope == pytest.approx(2.0)
    assert fit.intercept == pytest.approx(100.0)
    assert fit.r2 == pytest.approx(1.0)
    assert len(fit.shared_barcodes) == 20


def test_align_barcodes_uses_only_shared_barcode_values():
    # VR side is missing the first 3 barcode values, NP side the last 3.
    vr_times, vr_values, np_times, np_values = _linear_barcode_streams(
        n=20, skip_vr=3
    )
    np_values = np_values[:-3]
    np_times = np_times[:-3]

    fit = align_barcodes(vr_times, vr_values, np_times, np_values)

    assert len(fit.shared_barcodes) == 14  # 20 - 3 leading - 3 trailing
    assert fit.slope == pytest.approx(2.0)


def test_align_barcodes_skip_first_n_excludes_leading_vr_events():
    vr_times, vr_values, np_times, np_values = _linear_barcode_streams(n=20)
    # Corrupt the first two VR onset times so an unskipped fit would be biased.
    vr_times = vr_times.copy()
    vr_times[:2] += 1000.0

    biased_fit = align_barcodes(vr_times, vr_values, np_times, np_values)
    assert biased_fit.slope != pytest.approx(2.0)

    corrected_fit = align_barcodes(
        vr_times, vr_values, np_times, np_values, skip_first_n_barcodes=2
    )
    assert corrected_fit.slope == pytest.approx(2.0)
    assert corrected_fit.intercept == pytest.approx(100.0)
    assert len(corrected_fit.shared_barcodes) == 18


def test_align_barcodes_interpol_func_maps_vr_time_to_np_time():
    vr_times, vr_values, np_times, np_values = _linear_barcode_streams(
        slope=2.0, intercept=100.0
    )

    fit = align_barcodes(vr_times, vr_values, np_times, np_values)

    assert fit.interpol_func(5.0) == pytest.approx(110.0)

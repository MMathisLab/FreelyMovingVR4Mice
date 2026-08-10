"""Unit tests for latency_testing.py signal alignment helpers."""

import numpy as np

from latency_testing import get_signals


def _build_proc_like_data():
    """Create minimal synthetic PROC-like payload for get_signals."""
    # Dense photodiode sampling to exercise filtering and thresholding paths.
    photodiode_time = np.linspace(0.0, 5.0, 5001)
    photodiode_read = np.zeros_like(photodiode_time)
    photodiode_read[2200:2600] = 10.0

    # Intentionally off-by-one generated arrays (real-world mismatch case).
    generated_frame_time = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    generated_send_time = np.array([0.01, 1.01, 2.01, 3.01, 4.01, 5.01])
    generated_signal = np.array([0.0, 0.0, 1.0, 1.0, 0.0, 0.0])

    return {
        "photodiode_read": photodiode_read,
        "photodiode_time": photodiode_time,
        "start_time": 0.0,
        "generated_frame_time": generated_frame_time,
        "generated_send_time": generated_send_time,
        "generated_signal": generated_signal,
    }


def test_get_signals_handles_off_by_one_generated_lengths():
    """get_signals should align generated arrays and avoid broadcast errors."""
    data = _build_proc_like_data()

    df = get_signals(data)

    assert not df.empty
    assert "signal_read" in df.columns
    assert "photodiode_read" in df.columns
    assert df["signal_read"].notna().any()

"""Unit tests for plotting.py numerical helpers."""

import sys
import types

import numpy as np

# plotting.py imports seaborn at module import time; helper tests do not use it.
if "seaborn" not in sys.modules:
    sys.modules["seaborn"] = types.ModuleType("seaborn")

from plotting import _safe_sem, _safe_se_interval, plot_aligned_summary


def test_safe_sem_returns_nan_for_single_value():
    """SEM should be NaN for singleton inputs to avoid divide-by-zero warnings."""
    result = _safe_sem([1.0])

    assert np.isnan(result)


def test_safe_sem_matches_expected_for_multiple_values():
    """SEM should be finite when at least two non-NaN values are present."""
    result = _safe_sem([1.0, 3.0, np.nan])

    assert np.isfinite(result)
    assert np.isclose(result, 1.0)


def test_safe_se_interval_returns_nan_bounds_for_single_value():
    """SE interval should return NaN bounds for singleton inputs."""
    low, high = _safe_se_interval([2.0])

    assert np.isnan(low)
    assert np.isnan(high)


def test_safe_se_interval_returns_mean_plus_minus_sem():
    """SE interval should be mean +/- SEM for valid multi-sample inputs."""
    low, high = _safe_se_interval([1.0, 3.0, np.nan])

    assert np.isfinite(low)
    assert np.isfinite(high)
    assert np.isclose(low, 1.0)
    assert np.isclose(high, 3.0)


def test_plot_aligned_summary_draws_apertures_reference_and_pooled():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    time = [0.0, 1.0]
    summary = pd.concat(
        [
            pd.DataFrame(
                {
                    "kind": kind,
                    "aperture": aperture,
                    "time": time,
                    "mean": [0.0, 1.0],
                    "sem": [0.1, 0.1],
                    "n_sessions": 2,
                }
            )
            for kind, aperture in [
                ("aperture", 3.0),
                ("aperture", 4.3),
                ("ref", 12.0),
                ("pooled", np.nan),
            ]
        ]
    )
    fig, ax = plt.subplots()
    plot_aligned_summary(
        ax, summary, {3.0: "red", 4.3: "blue"}, ref_aperture=12.0, labels={3.0: "tight"}
    )
    labels = [
        line.get_label() for line in ax.lines if not line.get_label().startswith("_")
    ]
    assert labels == ["tight", "4.3", "12 (ref)", "< 12 pooled"]
    assert len(ax.collections) == 1  # the pooled SEM band
    plt.close(fig)

"""Unit tests for plotting.py numerical helpers."""

import numpy as np

from plotting import _safe_sem


def test_safe_sem_returns_nan_for_single_value():
    """SEM should be NaN for singleton inputs to avoid divide-by-zero warnings."""
    result = _safe_sem([1.0])

    assert np.isnan(result)


def test_safe_sem_matches_expected_for_multiple_values():
    """SEM should be finite when at least two non-NaN values are present."""
    result = _safe_sem([1.0, 3.0, np.nan])

    assert np.isfinite(result)
    assert np.isclose(result, 1.0)

"""Unit tests for regression.py decision-model helpers."""

import numpy as np
import pandas as pd

from regression import (
    _minmax_scale_series,
    compute_bic,
    compute_bic_sliding_window,
    predict_decision,
)


def _synthetic_decision_df(n_sessions=2, n_trials=4, n_steps=5):
    rng = np.random.default_rng(0)
    rows = []
    for session_idx in range(n_sessions):
        dataset = f"Mouse_2024-01-0{session_idx + 1}_1"
        for trial in range(n_trials):
            choice = int(trial % 2)
            for step in range(n_steps):
                rows.append(
                    {
                        "dataset": dataset,
                        "trial": trial,
                        "trial_length": step / n_steps,
                        "trial_left_choice": choice,
                        "norm_x": rng.normal(choice, 0.5),
                        "norm_y": rng.normal(1 - choice, 0.5),
                    }
                )
    return pd.DataFrame(rows)


class TestPredictDecision:
    def test_returns_three_values(self):
        df = _synthetic_decision_df()
        result = predict_decision(
            df,
            label=["norm_x", "norm_y"],
            per_mouse=True,
            scale_data=True,
            random_state=0,
        )
        assert len(result) == 3

    def test_output_columns_and_scalers(self):
        df = _synthetic_decision_df()
        df_model, coef, scalers = predict_decision(
            df,
            label=["norm_x", "norm_y"],
            per_mouse=True,
            scale_data=True,
            random_state=0,
        )

        assert {"proba_left", "accuracy"}.issubset(df_model.columns)
        assert coef.shape == (2, 3)
        assert len(scalers) == 2
        assert all("mean" in s and "scale" in s for s in scalers)

    def test_scaler_fit_on_train_fold_only(self):
        df = _synthetic_decision_df(n_sessions=2, n_trials=6, n_steps=8)
        _, _, scalers = predict_decision(
            df,
            label=["norm_x", "norm_y"],
            per_mouse=True,
            scale_data=True,
            random_state=0,
        )

        for session_idx, scaler in enumerate(scalers):
            train_mask = df["dataset"] != f"Mouse_2024-01-0{session_idx + 1}_1"
            expected_mean = df.loc[train_mask, ["norm_x", "norm_y"]].mean().to_numpy()
            np.testing.assert_allclose(scaler["mean"], expected_mean, rtol=1e-5)


class TestComputeBic:
    def test_sliding_window_uses_exact_window_size(self):
        probs = np.column_stack([np.linspace(0.1, 0.9, 12), np.linspace(0.9, 0.1, 12)])
        y = np.array([0, 1] * 6)
        bic = compute_bic_sliding_window(probs, y, n_params=3, window_size=4)

        assert len(bic) == len(y)
        assert np.isfinite(bic).all()

    def test_sliding_window_empty_input(self):
        bic = compute_bic_sliding_window(np.array([]), np.array([]), n_params=2)
        assert bic.size == 0

    def test_compute_bic_requires_both_labels(self):
        probs = np.column_stack([np.full(5, 0.2), np.full(5, 0.8)])
        y = np.ones(5, dtype=int)
        bic = compute_bic(probs, y, n_params=2)
        assert np.isfinite(bic)


class TestMinMaxScaleSeries:
    def test_scales_to_unit_interval(self):
        series = pd.Series([1.0, 2.0, 3.0])
        scaled = _minmax_scale_series(series)
        pd.testing.assert_series_equal(
            scaled, pd.Series([0.0, 0.5, 1.0]), check_names=False
        )

    def test_constant_series_returns_zeros(self):
        series = pd.Series([2.0, 2.0, 2.0])
        scaled = _minmax_scale_series(series)
        pd.testing.assert_series_equal(
            scaled, pd.Series([0.0, 0.0, 0.0]), check_names=False
        )

"""Unit tests for regression.py decision-model helpers."""

import numpy as np
import pandas as pd

from regression import (
    _minmax_scale_series,
    compute_bic,
    compute_bic_sliding_window,
    predict_decision,
    prepare_trial_model_features,
    rank_turning_thresholds,
    rank_window_models,
    summarize_window_prediction,
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


def test_window_summary_weights_windows_equally_and_takes_cv_across_trials():
    predictions = pd.DataFrame(
        {
            "dataset": ["a", "a", "a", "a", "a", "b", "b"],
            "trial": [1, 1, 1, 2, 2, 1, 2],
            "model_idx": [0, 9, 9, 9, 9, 9, 9],
            "accuracy": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "bic": [30.0, 10.0, 10.0, 20.0, 20.0, 30.0, 30.0],
        }
    )
    summary, windows = summarize_window_prediction(
        predictions, final_window=9, include_windows=True
    )
    assert summarize_window_prediction(predictions, final_window=9) == summary
    # Final window: session a has trial BICs [10, 20], session b [30, 30];
    # trials sharing a number across sessions are not paired.
    expected_cv = (np.std([10.0, 20.0], ddof=1) / 15.0 + 0.0) / 2
    assert summary["accuracy"] == 0.5
    assert summary["bic"] == 25.0
    assert np.isclose(summary["cv_end"], expected_cv)
    assert windows["model_idx"].tolist() == [0, 9]
    assert windows["bic"].tolist() == [30.0, 20.0]
    assert np.isclose(
        windows.loc[windows["model_idx"] == 9, "coef_var_bic"].item(), expected_cv
    )


def test_model_ranking_matches_notebook_composite():
    metrics = pd.DataFrame(
        {
            "label_set_id": [8, 1, 3, 4, 2, 5, 6, 7, 9],
            "param_id": [1] * 9,
            "accuracy": [
                0.857214,
                0.852138,
                0.845184,
                0.851404,
                0.784125,
                0.851274,
                0.859978,
                0.625270,
                0.99,
            ],
            "bic": [
                17.155089,
                17.375687,
                12.991663,
                18.002356,
                15.272077,
                33.294042,
                40.030106,
                23.043837,
                1,
            ],
            "cv_end": [
                0.001278,
                0.001122,
                0.053966,
                0.021914,
                0.003919,
                0.000562,
                0.000436,
                0.205756,
                np.nan,
            ],
        }
    )
    ranked = rank_window_models(metrics)
    assert ranked["label_set_id"].tolist() == [8, 1, 3, 4, 2, 5, 6, 7]
    np.testing.assert_allclose(ranked["score"].iloc[0], 0.943381, atol=1e-5)
    np.testing.assert_allclose(
        ranked["score"], ranked[["accuracy_norm", "bic_norm", "cv_norm"]].mean(axis=1)
    )
    assert np.isfinite(rank_window_models(metrics.iloc[:1])["score"].iloc[0])


def test_turning_threshold_uses_mean_over_finite_session_scores():
    evaluations = pd.DataFrame(
        {
            "threshold": ["0.2", "0.2", "0.1", "0.1", "0.3", "0.4"],
            "jump_score_norm": [3.0, 1.0, 2.0, 2.0, np.inf, np.nan],
            "n_trials": [200, 2, 20, 30, 1, 1],
        }
    )
    assert rank_turning_thresholds(evaluations).to_dict() == {"0.1": 2.0, "0.2": 2.0}


def test_trial_model_features_keep_sessions_separate():
    trials = pd.DataFrame(
        {
            "dataset": ["a", "a", "b", "a", "b", "b"],
            "trial": [2, 2, 1, 1, 2, 2],
            "trial_left_choice": [0, 0, 0, 1, 1, 1],
            "x": [1, 2, 3, 4, 5, 6],
            "y": [6, 5, 4, 3, 2, 1],
        }
    )
    features = prepare_trial_model_features(
        trials, ["trial_init_x", "trial_init_y", "trial_history"]
    )
    assert features["trial_init_x"].tolist() == [1, 1, 3, 4, 5, 5]
    assert features["trial_init_y"].tolist() == [6, 6, 4, 3, 2, 2]
    assert features["trial_history"].tolist() == [1, 1, 0, 0, 0, 0]
    assert "trial_history" not in trials

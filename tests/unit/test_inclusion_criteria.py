"""Unit tests for the reward-based session inclusion criteria."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

UTILS_PATH = (
    Path(__file__).resolve().parents[2]
    / "dj_pipeline"
    / "vr4mice"
    / "analysis"
    / "utils.py"
)


@pytest.fixture(scope="module")
def utils_module():
    spec = importlib.util.spec_from_file_location("inclusion_utils", UTILS_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"vr4mice.analysis.analysis": MagicMock()}):
        spec.loader.exec_module(module)
    return module


@pytest.fixture
def apply_inclusion_criteria(utils_module):
    return utils_module.apply_inclusion_criteria


def _trials(rewards):
    """One trial per dataset and aperture whose reward is the session mean."""
    return pd.DataFrame(
        [
            {"dataset": dataset, "aperture": aperture, "trial": i, "trial_rewarded": r}
            for dataset, by_aperture in rewards.items()
            for i, (aperture, r) in enumerate(by_aperture.items())
        ]
    )


# Narrow (4.3) and wide (12.0) rewards printed in Paper_figures/Figure_3.ipynb.
PAPER_SESSIONS = {
    "J731_2024-12-04_1": {4.3: 0.705882, 12.0: 0.636364},  # wide reward too low
    "J731_2024-12-05_1": {4.3: 0.769231, 12.0: 0.739130},  # included
    "J731_2024-12-09_1": {4.3: 0.542857, 12.0: 0.797468},  # drop 0.255
    "J729_2024-11-29_1": {4.3: 0.653846, 12.0: 0.500000},  # wide reward too low
    "31728_2025-03-06_1": {4.3: 0.507246, 12.0: 0.820225},  # drop 0.313
}


def _included(apply, rewards, **criteria):
    _, table, details = apply(_trials(rewards), return_details=True, **criteria)
    return set(table.index[table["included_by_criteria"]]), details


def test_defaults_reproduce_the_published_selection(apply_inclusion_criteria):
    included, details = _included(apply_inclusion_criteria, PAPER_SESSIONS)

    assert included == {"J731_2024-12-05_1"}
    assert details == {
        "min_reward": 0.7,
        "reward_basis": "widest",
        "max_reward_drop": 0.25,
        "consider_reward_drop": True,
        "min_narrow_reward": None,
        "narrowest_aperture": 4.3,
        "widest_aperture": 12.0,
        "aperture_values": [4.3, 12.0],
    }


def test_best_extreme_basis_accepts_a_high_narrow_reward(apply_inclusion_criteria):
    included, _ = _included(
        apply_inclusion_criteria, PAPER_SESSIONS, reward_basis="best_extreme"
    )

    assert included == {"J731_2024-12-04_1", "J731_2024-12-05_1"}


def test_narrow_reward_floor_passes_the_drop_criterion(apply_inclusion_criteria):
    rewards = {
        **PAPER_SESSIONS,
        "Xestia_2026-07-28_1": {4.3: 0.629032, 12.0: 0.943089},  # drop 0.314
    }

    included, details = _included(
        apply_inclusion_criteria, rewards, min_narrow_reward=0.55
    )

    assert included == {"J731_2024-12-05_1", "Xestia_2026-07-28_1"}
    assert details["min_narrow_reward"] == 0.55


def test_missing_extreme_aperture_excludes_the_dataset(apply_inclusion_criteria):
    rewards = {"full": {4.3: 0.8, 12.0: 0.9}, "no_narrow": {12.0: 0.9}}

    filtered, table = apply_inclusion_criteria(_trials(rewards))

    assert set(filtered.dataset) == {"full"}
    assert not table["included_by_criteria"]["no_narrow"]


def test_rejects_unknown_reward_basis(apply_inclusion_criteria):
    with pytest.raises(ValueError, match="reward_basis"):
        apply_inclusion_criteria(_trials(PAPER_SESSIONS), reward_basis="narrowest")


# Narrow (4.3) and wide (12.0) rewards of the batch2 dual-occlusion sessions.
BATCH2_DUAL_OCCLUSION = {
    "Xestia_2026-07-27_1": {4.3: 0.570312, 12.0: 0.844828},
    "Xestia_2026-07-28_1": {4.3: 0.629032, 12.0: 0.943089},
    "Xestia_2026-07-29_1": {4.3: 0.620438, 12.0: 0.889908},
    "Xestia_2026-07-30_1": {4.3: 0.715596, 12.0: 0.897059},
    "Yurumi_2026-07-29_1": {4.3: 0.639344, 12.0: 0.653226},
    "Yurumi_2026-07-30_1": {4.3: 0.736000, 12.0: 0.672269},
    "Yurumi_2026-07-31_1": {4.3: 0.690476, 12.0: 0.791667},
    "Yurumi_2026-08-03_1": {4.3: 0.626984, 12.0: 0.800000},
}


# Narrow (3.0, fully occluded) and wide (12.0) rewards of the batch2
# multi-occlusion sessions.
BATCH2_MULTI_OCCLUSION = {
    "Xestia_2026-07-31_1": {3.0: 0.550000, 12.0: 0.823529},  # drop 0.274
    "Xestia_2026-08-03_1": {3.0: 0.627907, 12.0: 0.795918},
    "Xestia_2026-08-04_1": {3.0: 0.512821, 12.0: 0.719298},
    "Xestia_2026-08-05_1": {3.0: 0.650000, 12.0: 0.820000},
    "Yurumi_2026-08-04_1": {3.0: 0.581818, 12.0: 0.846154},  # drop 0.264
    "Yurumi_2026-08-05_1": {3.0: 0.604651, 12.0: 0.812500},
    "Yurumi_2026-08-06_1": {3.0: 0.666667, 12.0: 0.829787},
    "Yurumi_2026-08-07_1": {3.0: 0.648649, 12.0: 0.879310},
}

# Mirrors InclusionStatus.criteria_by_batch["batch2"].
BATCH2_CRITERIA = {"reward_basis": "best_extreme", "min_narrow_reward": 0.5}


@pytest.mark.parametrize(
    "rewards, excluded",
    [
        (BATCH2_DUAL_OCCLUSION, {"Yurumi_2026-07-29_1"}),
        (BATCH2_MULTI_OCCLUSION, set()),
    ],
    ids=["dual_occlusion", "multi_occlusion"],
)
def test_batch2_criteria(apply_inclusion_criteria, rewards, excluded):
    included, _ = _included(apply_inclusion_criteria, rewards, **BATCH2_CRITERIA)

    assert included == set(rewards) - excluded


def test_narrow_reward_floor_is_strict(apply_inclusion_criteria):
    rewards = {"at_chance": {3.0: 0.5, 12.0: 0.9}, "above": {3.0: 0.51, 12.0: 0.9}}

    included, _ = _included(apply_inclusion_criteria, rewards, **BATCH2_CRITERIA)

    assert included == {"above"}


def test_trial_rewards_are_averaged_within_then_across_trials(
    apply_inclusion_criteria,
):
    # Two rows for trial 0 (mean 1.0) and one for trial 1 (0.0): mean 0.5, not
    # the row mean of 2/3. A missing reward is ignored.
    data = pd.DataFrame(
        {
            "dataset": ["d"] * 5,
            "aperture": [4.3, 4.3, 4.3, 12.0, 12.0],
            "trial": [0, 0, 1, 2, 3],
            "trial_rewarded": [1.0, 1.0, 0.0, 1.0, float("nan")],
        }
    )

    _, table = apply_inclusion_criteria(data)

    assert table["trial_rewarded"].loc["d"].tolist() == [0.5, 1.0]


def test_aperture_float_noise_is_merged(apply_inclusion_criteria):
    data = _trials({"d": {4.3: 0.8, 12.0: 0.9}})
    data = pd.concat(
        [data, data.assign(aperture=data.aperture + 1e-9, trial=data.trial + 10)]
    )

    _, _, details = apply_inclusion_criteria(data, return_details=True)

    assert details["aperture_values"] == [4.3, 12.0]


def test_all_missing_rewards_at_an_extreme_exclude_with_a_warning(utils_module):
    data = _trials({"ok": {4.3: 0.8, 12.0: 0.9}, "nan": {4.3: 0.8, 12.0: 0.9}})
    data.loc[(data.dataset == "nan") & (data.aperture == 4.3), "trial_rewarded"] = (
        float("nan")
    )
    utils_module.logger.reset_mock()

    filtered, _ = utils_module.apply_inclusion_criteria(data)

    assert set(filtered.dataset) == {"ok"}
    message = utils_module.logger.warning.call_args.args
    assert "nan" in message[-1]


def test_floor_is_ignored_without_the_drop_criterion(apply_inclusion_criteria):
    rewards = {"big_drop": {4.3: 0.4, 12.0: 0.9}}

    included, _ = _included(
        apply_inclusion_criteria,
        rewards,
        consider_reward_drop=False,
        min_narrow_reward=0.5,
    )

    assert included == {"big_drop"}


def test_return_excluded_returns_the_complement(apply_inclusion_criteria):
    data = _trials(PAPER_SESSIONS)

    kept, _ = apply_inclusion_criteria(data)
    dropped, _ = apply_inclusion_criteria(data, return_excluded=True)

    assert set(kept.dataset) | set(dropped.dataset) == set(PAPER_SESSIONS)
    assert not set(kept.dataset) & set(dropped.dataset)


@pytest.mark.parametrize(
    "data, criteria, match",
    [
        (_trials({"d": {4.3: 0.8}}), {}, "occluder sizes"),
        (_trials({"d": {4.3: 0.8, 12.0: 0.9}}).iloc[:0], {}, "No trials"),
        (_trials({"d": {4.3: 0.8, 12.0: 0.9}}).drop(columns="trial"), {}, "columns"),
        (
            _trials({"d": {4.3: 0.8, 12.0: 0.9}}).assign(aperture="wide"),
            {},
            "numeric",
        ),
        (_trials({"d": {4.3: 0.8, 12.0: 0.9}}), {"min_reward": 70}, "min_reward"),
        (
            _trials({"d": {4.3: 0.8, 12.0: 0.9}}),
            {"max_reward_drop": -0.1},
            "max_reward_drop",
        ),
        (
            _trials({"d": {4.3: 0.8, 12.0: 0.9}}),
            {"min_narrow_reward": float("nan")},
            "min_narrow_reward",
        ),
    ],
    ids=[
        "one_aperture",
        "empty",
        "missing_column",
        "text_aperture",
        "min_reward_percent",
        "negative_drop",
        "nan_floor",
    ],
)
def test_invalid_inputs_raise(apply_inclusion_criteria, data, criteria, match):
    with pytest.raises(ValueError, match=match):
        apply_inclusion_criteria(data, **criteria)

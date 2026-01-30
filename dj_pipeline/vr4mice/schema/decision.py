"""Decision analysis schema for regression models and decision points."""

import datajoint as dj
import pandas as pd
import numpy as np

from vr4mice.analysis import regression

from vr4mice.schema import vr4mice
from vr4mice.schema.vr4mice import Dataset
from vr4mice.schema.session_metrics import TrialMetrics
from vr4mice.schema.interpolated_trajectories import InterpolatedTrials

from vr4mice.utils.logger import Logger

from vr4mice.utils.schema_config import get_schema

schema_name = "decision"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()


@schema
class TrainingGroup(dj.Lookup):
    definition = """
    -> Dataset
    """


@schema
class DualGroup(dj.Lookup):
    definition = """
    session_label : varchar(64)    # session label for dual occluder task
    """
    contents = [
        ("ar_discrim_occluders"),
        ("ar_shape_discrim_narrow_occluders"),
        ("ar_discrim_occluders_inv"),
    ]


@schema
class MultiGroup(dj.Lookup):
    definition = """
    session_label : varchar(64)    # session label for multi occluder task
    """
    contents = [
        ("ar_discrim_5_occluders"),
        ("ar_shape_discrim_multi_occluders"),
        ("ar_discrim_5_occluders_inv"),
    ]


@schema
class ValidGroup(dj.Computed):
    """Define groups of mice for occluder analysis."""

    definition = """
    -> Dataset
    -> TrialMetrics
    ---
    dual_occl : int     # 1 if valid for dual occluder task, 0 otherwise
    multi_occl : int     # 1 if valid for multi occluder task, 0 otherwise
    """

    # key is not in TrainingGroup
    _key_source = Dataset() - TrainingGroup()

    def make(self, key):
        """Mark datasets that meet inclusion criteria for occluder tasks."""
        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            trial_df = (TrialMetrics() * (Dataset() & key)).fetch(as_dict=True)
            trial_df = pd.concat([pd.DataFrame(x) for x in trial_df])
            trial_df["aperture"] = trial_df.aperture.round(2)

            trial_df = trial_df[trial_df["dataset"] != "Lemming_2024-08-09_1"]

            # Exclude sessions that were not in the list
            from vr4mice.analysis.utils import apply_inclusion_criteria

            if trial_df["session_label"].iloc[0] in DualGroup().fetch("session_label"):
                trial_df, _ = apply_inclusion_criteria(
                    trial_df, task_type="dual_occluder"
                )

                if not trial_df.empty:
                    self.insert1({**key, "dual_occl": 1, "multi_occl": 0})
                else:
                    self.insert1({**key, "dual_occl": 0, "multi_occl": 0})
            elif trial_df["session_label"].iloc[0] in MultiGroup().fetch(
                "session_label"
            ):
                trial_df, _ = apply_inclusion_criteria(
                    trial_df, task_type="multi_occluder"
                )

                if not trial_df.empty:
                    self.insert1({**key, "dual_occl": 0, "multi_occl": 1})
                else:
                    self.insert1({**key, "dual_occl": 0, "multi_occl": 0})

            else:
                TrainingGroup().insert1({**key})
                return
        except Exception as err:
            dataset = key.get("dataset") if isinstance(key, dict) else None
            if dataset:
                vr4mice.FailedSession().add_entry(
                    f"{dataset}", f"{self.__class__.__name__}", str(err)
                )
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None


@schema
class Label(dj.Lookup):
    definition = """
    label_key : varchar(32)    # internal short name (e.g., 'velocity_x')
    ---
    clean_name : varchar(64)   # display name (e.g., 'x velocity')
    """
    contents = [
        ("x", "x position"),
        ("y", "y position"),
        ("velocity_x", "x velocity"),
        ("velocity_y", "y velocity"),
        ("heading_dir_sin", "sin(running direction)"),
        ("heading_dir_cos", "cos(running direction)"),
        ("head_angle_sin", "sin(head-body angle)"),
        ("head_angle_cos", "cos(head-body angle)"),
        ("trial_tortuosity", "Trial tortuosity"),
        ("trial_rewarded", "Trial rewarded"),
        ("trial_length", "Trial progression"),
        ("trial_init_x", "Trial initial x position"),
        ("trial_init_y", "Trial initial y position"),
        ("trial_history", "Previous trial choice"),
    ]


@schema
class LabelSet(dj.Lookup):
    definition = """
    label_set_id : int
    ---
    label_set_name : varchar(64)
    """

    class Member(dj.Part):
        definition = """
        -> master             # Links to label_set_id
        -> Label              # Links to label_key in the Label table
        """

    @classmethod
    def fill(cls):
        custom_sets = {
            1: ("Kinematics only", ["x", "y", "velocity_x", "velocity_y"]),
            2: ("Position + Reward", ["x", "y", "trial_rewarded"]),
            3: ("Velocity only", ["velocity_x", "velocity_y"]),
            4: (
                "sin & cos only",
                [
                    "heading_dir_sin",
                    "heading_dir_cos",
                    "head_angle_sin",
                    "head_angle_cos",
                ],
            ),
            5: (
                "Baseline",
                [
                    "x",
                    "y",
                    "velocity_x",
                    "velocity_y",
                    "heading_dir_sin",
                    "heading_dir_cos",
                    "head_angle_sin",
                    "head_angle_cos",
                    "trial_tortuosity",
                    "trial_rewarded",
                    "trial_length",
                ],
            ),
            6: (
                "All",
                [
                    "x",
                    "y",
                    "velocity_x",
                    "velocity_y",
                    "heading_dir_sin",
                    "heading_dir_cos",
                    "head_angle_sin",
                    "head_angle_cos",
                    "trial_tortuosity",
                    "trial_rewarded",
                    "trial_length",
                    "trial_init_x",
                    "trial_init_y",
                    "trial_history",
                ],
            ),
            7: (
                "Best on baseline",
                [
                    "x",
                    "velocity_x",
                    "heading_dir_sin",
                    "head_angle_sin",
                    "trial_rewarded",
                ],
            ),
            8: ("History only", ["trial_history"]),
            9: ("Initial position only", ["trial_init_x", "trial_init_y"]),
        }

        for set_id, (name, labels) in custom_sets.items():
            cls.insert1(
                {"label_set_id": set_id, "label_set_name": name}, skip_duplicates=True
            )

            # The 'label_key' here must exist in the Label table contents
            member_entries = [
                {"label_set_id": set_id, "label_key": lbl} for lbl in labels
            ]
            cls.Member.insert(member_entries, skip_duplicates=True)


@schema
class ModelParams(dj.Lookup):
    definition = """
    param_id : int          # unique ID for hyperparam combo
    ---
    max_iter : int          # maximum number of iterations for logistic regression
    scale_data : bool       # whether to scale data before training
    """
    contents = [
        (1, 100, True),
    ]


@schema
class TaskType(dj.Lookup):
    definition = """
    task_type : varchar(32)      # type of task (e.g., dual_occl, multi_occl)
    ---
    description : varchar(255)   # description of the task type
    """
    contents = [
        ("dual_occl", "Dual occluder discrimination task"),
        ("multi_occl", "Multi occluder discrimination task"),
    ]


@schema
class PredictionModel(dj.Computed):
    """Train logistic regression model per mouse using LOGO cross-validation."""

    definition = """
    -> LabelSet
    -> ModelParams
    -> TaskType
    ---
    coefficients : longblob     # coefficients per session (per_mouse=True)
    n_sessions : int            # number of sessions included
    sessions : longblob         # list of session dataset names
    random_state : int          # random state used for reproducibility
    mean_accuracy : float       # mean accuracy across sessions
    bic : float                 # Bayesian Information Criterion for the model
    """

    class SessionPrediction(dj.Part):
        definition = """
        -> master
        -> Dataset
        ---
        n_samples : int                # number of samples in the session
        mean_accuracy : float          # mean accuracy for this session
        mean_proba_left: float         # mean predicted probability for left choice
        trial : longblob               # trial numbers
        trial_length: longblob         # trial progression
        proba_left : longblob          # predicted probabilities for left choice
        accuracy : longblob            # per-trial accuracy values
        trial_left_choice : longblob   # ground truth left choice
        bic : longblob                 # Bayesian Information Criterion per timestep
        """

    def make(self, key):
        """Train regression model and store per-session predictions."""
        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            # Get label set and model params
            label_set = list((LabelSet.Member & key).fetch("label_key"))
            params = (ModelParams & key).fetch(as_dict=True)[0]
            task_type = (TaskType & key).fetch1("task_type")

            sessions_list = list((ValidGroup & f"{task_type}=1").fetch("dataset"))

            # This takes a while to fetch because we need to fetch data from all sessions
            dataset_list = []
            for d in sessions_list:
                if len(InterpolatedTrials() & f'dataset = "{d}"') > 0:
                    dataset_list.append(
                        pd.DataFrame(
                            (InterpolatedTrials() & f'dataset = "{d}"').fetch(
                                as_dict=True
                            )[0]
                        )
                    )
                else:
                    raise ValueError(f"InterpolatedTrials missing for {d}")

            interpolated_df = pd.concat(dataset_list)
            interpolated_df["mouse_name"] = interpolated_df.dataset.str.split("_").str[
                0
            ]
            interpolated_df["aperture"] = interpolated_df["aperture"].astype(float)

            if "trial_init_x" in label_set:
                interpolated_df["trial_init_x"] = interpolated_df.groupby(
                    ["dataset", "trial"]
                )["x"].transform("first")

            if "trial_init_y" in label_set:
                interpolated_df["trial_init_y"] = interpolated_df.groupby(
                    ["dataset", "trial"]
                )["y"].transform("first")

            if "trial_history" in label_set:
                interpolated_df["trial_history"] = interpolated_df.groupby(
                    ["dataset", "trial"]
                )["trial_left_choice"].transform(lambda x: x.shift(1).fillna(0))

            random_state = 42

            # Train model using LOGO cross-validation across sessions
            df_model, coef = regression.predict_decision(
                df=interpolated_df,
                label=label_set,
                per_mouse=True,
                max_iter=params["max_iter"],
                scale_data=params["scale_data"],
                random_state=random_state,
            )

            # Aggregate predictions per trial for BIC calculation (use mean probability per trial)
            df_model_per_trial = (
                df_model.groupby(["dataset", "trial"])
                .agg(
                    {
                        "proba_left": "mean",
                        "accuracy": "mean",
                        "trial_left_choice": "first",
                        "trial_length": "first",
                    }
                )
                .reset_index()
            )

            # Across all sessions BIC
            bic = regression.compute_bic(
                df_model_per_trial["proba_left"].values.reshape(-1, 1),
                df_model_per_trial["trial_left_choice"].values,
            )

            self.insert1(
                {
                    **key,
                    "coefficients": coef,
                    "n_sessions": len(sessions_list),
                    "sessions": sessions_list,
                    "random_state": random_state,
                    "mean_accuracy": float(df_model_per_trial["accuracy"].mean()),
                    "bic": bic,
                }
            )

            # Insert per-session predictions
            for dataset in df_model["dataset"].unique():
                dataset_trials = df_model[df_model["dataset"] == dataset].reset_index(
                    drop=True
                )

                bic_per_timestep = np.full(len(dataset_trials), np.nan)
                for trial in dataset_trials["trial"].unique():
                    trial_df = dataset_trials[dataset_trials["trial"] == trial]

                    # Compute BIC per timestep using sliding window
                    bic_per_timestep[
                        trial_df.index
                    ] = regression.compute_bic_sliding_window(
                        trial_df["proba_left"].values.reshape(-1, 1),
                        trial_df["trial_left_choice"].values,
                        window_size=10,
                    )

                self.SessionPrediction.insert1(
                    {
                        **key,
                        "dataset": dataset,
                        "n_samples": len(dataset_trials),
                        "mean_accuracy": float(dataset_trials["accuracy"].mean()),
                        "mean_proba_left": float(dataset_trials["proba_left"].mean()),
                        "trial": dataset_trials["trial"].values,
                        "trial_length": dataset_trials["trial_length"].values,
                        "trial_left_choice": dataset_trials["trial_left_choice"].values,
                        "proba_left": dataset_trials["proba_left"].values,
                        "accuracy": dataset_trials["accuracy"].values,
                        "bic": bic_per_timestep,
                    }
                )
        except Exception as err:
            dataset = key.get("dataset") if isinstance(key, dict) else None
            if dataset:
                vr4mice.FailedSession().add_entry(
                    f"{dataset}", f"{self.__class__.__name__}", str(err)
                )
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None


@schema
class DecisionThreshold(dj.Lookup):
    """Lookup table for different uncertainty thresholds to define decision points."""

    definition = """
    threshold_uncertainty : varchar(10)    # uncertainty threshold used to define decision point
    ---
    description : varchar(255)             # description of the threshold
    """
    contents = [
        ("0.0", "Threshold at 0.0 uncertainty"),
        ("0.1", "Threshold at 0.1 uncertainty"),
        ("0.2", "Threshold at 0.2 uncertainty"),
        ("0.3", "Baseline threshold"),
        ("0.4", "Threshold at 0.4 uncertainty"),
        ("0.5", "Threshold at 0.5 uncertainty"),
        ("0.6", "Threshold at 0.6 uncertainty"),
        ("0.7", "Threshold at 0.7 uncertainty"),
        ("0.8", "Threshold at 0.8 uncertainty"),
        ("0.9", "Threshold at 0.9 uncertainty"),
        ("1.0", "Threshold at 1.0 uncertainty"),
    ]


@schema
class DecisionPoints(dj.Computed):
    """Decision point and corresponding per-trial data."""

    definition = """
    -> PredictionModel
    -> InterpolatedTrials
    -> DecisionThreshold
    ---
    trial: longblob                 # trial corresponding to the timestamp
    proba_left: longblob            # pred proba of the regression on decision side
    aperture: longblob              # occlusion size for the corresponding trial
    trial_left_choice: longblob     # ground truth on the decision side
    trial_rewarded: longblob        # 1 if trial was rewarded, else 0
    trial_length: longblob          # length of the trial at which decision was made
    x: longblob                     # x position of the decision point in the trial
    y: longblob                     # y position of the decision point in the trial
    """

    def make(self, key):
        """Compute decision points from model predictions and trials."""
        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            threshold_uncertainty = float(
                (DecisionThreshold & key).fetch1("threshold_uncertainty")
            )

            predictions_df = pd.DataFrame(
                (PredictionModel.SessionPrediction & key).fetch(
                    "dataset", "trial", "proba_left", "trial_length", as_dict=True
                )[0]
            )

            trial_fields = [
                "dataset",
                "trial_left_choice",
                "x",
                "y",
                "aperture",
                "trial_length",
                "trial",
            ]
            if "trial_rewarded" in InterpolatedTrials.heading.names:
                trial_fields.append("trial_rewarded")
            trial_df = pd.DataFrame(
                (InterpolatedTrials() & key).fetch(*trial_fields, as_dict=True)[0]
            )
            if "trial_rewarded" not in trial_df.columns:
                from vr4mice.schema import base_analysis

                df = base_analysis.DataFrame().get_data(key, ["trial", "reward"])
                rewarded = base_analysis.DataFrame().get_rewarded(key=key)
                if not isinstance(df, pd.DataFrame) or not isinstance(
                    rewarded, pd.Series
                ):
                    raise ValueError(
                        "Missing DataFrame data needed to compute trial_rewarded."
                    )
                rewarded_map = (
                    pd.DataFrame({"trial": df["trial"], "trial_rewarded": rewarded})
                    .groupby("trial")["trial_rewarded"]
                    .max()
                    .to_dict()
                )
                trial_df["trial_rewarded"] = np.array(
                    [rewarded_map.get(int(t), 0) for t in trial_df["trial"]]
                )

            merged_df = pd.merge(
                predictions_df, trial_df, on=["dataset", "trial", "trial_length"]
            )

            decision_points = regression.find_decision_point(
                merged_df, threshold_uncertainty=threshold_uncertainty
            )

            row = {
                **key,
                "trial": decision_points["trial"].to_numpy(),
                "proba_left": decision_points["proba_left"].to_numpy(),
                "aperture": decision_points["aperture"].to_numpy(),
                "trial_left_choice": decision_points["trial_left_choice"].to_numpy(),
                "trial_rewarded": decision_points["trial_rewarded"].to_numpy(),
                "trial_length": decision_points["trial_length"].to_numpy(),
                "x": decision_points["x"].to_numpy(),
                "y": decision_points["y"].to_numpy(),
            }
            self.insert1(row)
        except Exception as err:
            dataset = key.get("dataset") if isinstance(key, dict) else None
            if dataset:
                vr4mice.FailedSession().add_entry(
                    f"{dataset}", f"{self.__class__.__name__}", str(err)
                )
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

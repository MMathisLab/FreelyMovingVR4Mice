"""Decision analysis schema for regression models and decision points."""

import datajoint as dj
import pandas as pd
import numpy as np
import sklearn.preprocessing

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
class SessionLabel(dj.Lookup):
    """
    SessionLabel definition table:
    maps session labels to experiment set and stage
    """

    definition = """
    session_label : varchar(64)
    ---
    set_name : varchar(64)
    stage_name : varchar(32)
    """

    contents = [
        # Contrast task with white target
        ("ar_detection_no_velthr", "contrast_white_target", "training"),
        ("ar_detection_velthr", "contrast_white_target", "training"),
        ("ar_discrim", "contrast_white_target", "training"),
        ("ar_discrim_occluders", "contrast_white_target", "dual_occlusion"),
        ("ar_discrim_5_occluders", "contrast_white_target", "multi_occlusion"),
        # Contrast task with black target
        ("ar_det_no_velthr_inv", "contrast_black_target", "training"),
        ("ar_detection_velthr_inv", "contrast_black_target", "training"),
        ("ar_discrim_inv", "contrast_black_target", "training"),
        ("ar_discrim_occluders_inv", "contrast_black_target", "dual_occlusion"),
        ("ar_discrim_5_occluders_inv", "contrast_black_target", "multi_occlusion"),
        # Shape task with white pacman target
        ("ar_shape_detection_no_velthr", "shape_pacman_target", "training"),
        ("ar_shape_detection_velthr", "shape_pacman_target", "training"),
        ("ar_shape_discrimination", "shape_pacman_target", "training"),
        # Shape task with black teardrop target
        ("ar_shape_det_no_velthr_inv", "shape_black_teardrop_target", "training"),
        ("ar_shape_detection_velthr_inv", "shape_black_teardrop_target", "training"),
        ("ar_shape_discrimination_inv", "shape_black_teardrop_target", "training"),
        (
            "ar_shape_discrim_occluders_inv",
            "shape_black_teardrop_target",
            "dual_occlusion",
        ),
        # NOTE(celia): 2-stage occlusion for this task, first one is still training
        ("ar_shape_discrim_occluders", "shape_pacman_target", "training"),
        ("ar_shape_discrim_narrow_occluders", "shape_pacman_target", "dual_occlusion"),
        ("ar_shape_discrim_multi_occluders", "shape_pacman_target", "multi_occlusion"),
        # NOTE(celia): not part of any experiment set, but we want to exclude
        # these sessions so that properly computed in InclusionCriteria
        ("random_occluders", "random", "random_occlusion"),
        ("AR_VD_single_teardrop", "random", "random_occlusion"),
        ("AR_VD_blocks_training", "random", "random_occlusion"),
        ("AR_VD_single_teardrop_blocks", "random", "random_occlusion"),
    ]


@schema
class ExperimentSet(dj.Lookup):
    """
    ExperimentSet definition table:
    stores experiment set names and descriptions
    """

    definition = """
    set_name : varchar(64)
    ---
    description : varchar(255)
    """
    contents = [
        ("contrast_white_target", "Contrast task, white target"),
        ("contrast_black_target", "Contrast task, black target"),
        ("shape_pacman_target", "Shape task, pacman target"),
        ("shape_black_teardrop_target", "Shape task, black teardrop target"),
        ("random", "Excluded / random-occluder sessions (not in main experiment sets)"),
    ]


@schema
class ExperimentStage(dj.Lookup):
    """
    ExperimentStage definition table:
    stores experiment stage names and descriptions
    """

    definition = """
    stage_name : varchar(32)
    ---
    description : varchar(255)
    """
    contents = [
        ("training", "Training sessions"),
        ("dual_occlusion", "Dual occluder sessions"),
        ("multi_occlusion", "Multi occluder sessions"),
        ("random_occlusion", "Random occluder sessions (excluded from main sets)"),
    ]


def sync_lookup_contents():
    """Insert Lookup rows from class ``contents`` that are missing in the DB.

    DataJoint only loads ``contents`` when a Lookup table is first created.
    On deployed databases, new rows added to ``contents`` in code must be
    back-filled explicitly (parent rows before ``ExperimentMember.populate``).
    """
    for table in (ExperimentSet, ExperimentStage, SessionLabel):
        if table.contents:
            table.insert(table.contents, skip_duplicates=True)


@schema
class ExperimentMember(dj.Imported):
    """
    ExperimentMember definition table:
    links each dataset to an experiment set, stage, and session label
    """

    definition = """
    -> Dataset
    ---
    -> ExperimentSet
    -> ExperimentStage
    -> SessionLabel
    """

    def make(self, key):
        try:
            session_label = (Dataset & key).fetch1("session_label")

            if not session_label:
                raise ValueError(
                    f"Session label not found for dataset '{key['dataset']}' in Dataset table"
                )

            # Look up the mapping for this session label
            label_info = (SessionLabel & {"session_label": session_label}).fetch(
                as_dict=True
            )

            if not label_info or len(label_info) > 1:
                raise ValueError(
                    f"Session label '{session_label}' not found in SessionLabel table or multiple entries found"
                )

            label_info = label_info[0]

            self.insert1(
                {
                    "dataset": key["dataset"],
                    "set_name": label_info["set_name"],
                    "stage_name": label_info["stage_name"],
                    "session_label": session_label,
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
class InclusionStatus(dj.Computed):
    """Inclusion status per dataset and experiment set role."""

    definition = """
    -> ExperimentMember
    ---
    included : bool
    """

    def make(self, key):
        try:

            if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
                return

            logger.info(f"{self.__class__.__name__} population started for {key}.")

            # Get stage_name from ExperimentMember
            stage_name = (ExperimentMember & key).fetch1("stage_name")
            # session_label = (ExperimentMember & key).fetch1("session_label")

            if stage_name == "training":
                self.insert1({**key, "included": False})
                return

            # NOTE(celia): this is a fix to exclude datasets that were not manually added by tom
            # in the Groups() table, but this table was not consistently populated for all datasets
            # so we exclude these datasets in this hardcoded way for now
            # We could also drop the Groups table entirely if it's not used elsewhere
            # NOTE(celia): (update) for now kept, but the Groups table was dropped in the DJ 2.0 migration so the
            # code should get the correct set of datasets without it now.
            # if (
            #     session_label == "ar_discrim_occluders"
            #     or session_label == "ar_discrim_5_occluders"
            # ):
            #     tables = TrialMetrics() * vr4mice.Groups() * (Dataset() & key)
            # else:
            tables = TrialMetrics() * (Dataset() & key)

            trial_df = tables.fetch(as_dict=True)

            # NOTE(celia):
            # "Lemming_2024-08-09_1" and "Lemming_2024-08-09_2" were dropped through the Groups table for now,
            # but kept if we decide to drop it
            # "Hamster_2026-02-02_1" is missing the dlc data
            if not trial_df or key in [
                {"dataset": "Hamster_2026-02-02_1"},
                {"dataset": "Lemming_2024-08-09_1"},
                {"dataset": "Lemming_2024-08-09_2"},
            ]:
                self.insert1({**key, "included": False})
                return

            trial_df = pd.concat([pd.DataFrame(x) for x in trial_df])
            trial_df["aperture"] = trial_df["aperture"].round(2)

            from vr4mice.analysis.utils import apply_inclusion_criteria

            filtered_df, _ = apply_inclusion_criteria(trial_df)
            included = not filtered_df.empty
            self.insert1({**key, "included": included})
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
    """
    Label definition table:
    stores regression feature names used in decision analysis
    """

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
    """
    LabelSet definition table:
    stores named sets of regression labels for model training
    """

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
            2: ("Position only", ["x", "y"]),
            3: ("Velocity only", ["velocity_x", "velocity_y"]),
            4: (
                "Orientation only",
                [
                    "heading_dir_sin",
                    "heading_dir_cos",
                    "head_angle_sin",
                    "head_angle_cos",
                ],
            ),
            5: (
                "Task-related",
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
            7: ("Priors", ["trial_history", "trial_init_x", "trial_init_y"]),
            8: (
                "Lateral Kinematics",
                [
                    "x",
                    "velocity_x",
                    "heading_dir_sin",
                    "head_angle_sin",
                ],
            ),
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
    """
    ModelParams definition table:
    stores logistic regression hyperparameter combinations
    """

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
class PredictionModel(dj.Computed):
    """Train logistic regression model per mouse using LOGO cross-validation."""

    definition = """
    -> LabelSet
    -> ModelParams
    -> ExperimentSet
    -> ExperimentStage
    ---
    coefficients : <blob>     # coefficients per session (per_mouse=True)
    n_sessions : int            # number of sessions included
    sessions : <blob>         # list of session dataset names
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
        trial : <blob>               # trial numbers
        trial_length: <blob>         # trial progression
        proba_left : <blob>          # predicted probabilities for left choice
        accuracy : <blob>            # per-trial accuracy values
        trial_left_choice : <blob>   # ground truth left choice
        bic : <blob>                 # Bayesian Information Criterion per timestep
        """

    def make(self, key):
        """Train regression model and store per-session predictions."""
        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        logger.info(f"{self.__class__.__name__} population started for {key}.")

        try:
            # Skip training stage - only train models for dual_occlusion and multi_occlusion
            stage_name = (ExperimentStage & key).fetch1("stage_name")
            if stage_name == "training":
                logger.info(f"Skipping training stage for {self.__class__.__name__}")
                return

            # Get label set and model params
            label_set = list((LabelSet.Member & key).fetch("label_key"))
            params = (ModelParams & key).fetch(as_dict=True)[0]

            # Get included datasets for this experiment set and stage
            # Join with ExperimentMember to filter by set_name and stage_name
            sessions_list = list(
                (InclusionStatus * ExperimentMember & key & {"included": 1}).fetch(
                    "dataset"
                )
            )

            # Validate that we have valid sessions for this model
            if not sessions_list:
                raise ValueError(
                    f"No valid sessions found for {self.__class__.__name__} with key {key}"
                )

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
                trial_choices = (
                    interpolated_df.groupby(["dataset", "trial"], as_index=False)
                    .agg({"trial_left_choice": "first"})
                    .sort_values(["dataset", "trial"])
                )
                trial_choices["trial_history"] = (
                    trial_choices.groupby("dataset")["trial_left_choice"]
                    .shift(1)
                    .fillna(0)
                )
                interpolated_df = interpolated_df.merge(
                    trial_choices[["dataset", "trial", "trial_history"]],
                    on=["dataset", "trial"],
                    how="left",
                )

            random_state = 42

            # Train model using LOGO cross-validation across sessions
            df_model, coef, _ = regression.predict_decision(
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
                df_model_per_trial["proba_left"].values,
                df_model_per_trial["trial_left_choice"].values,
                n_params=len(label_set) + 1,
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
                        trial_df["proba_left"].values,
                        trial_df["trial_left_choice"].values,
                        n_params=len(label_set) + 1,
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


# Number of equally-spaced trial progress windows used throughout this module
WINDOW_COUNT = 10


@schema
class PredictionModel10Windows(dj.Computed):
    """Train LOGO regression models on 10 equally-spaced trial progress windows."""

    definition = """
    -> LabelSet
    -> ModelParams
    -> ExperimentSet
    -> ExperimentStage
    ---
    coefficients_by_window : <blob>    # dict mapping window_id (0-9) -> coefficients
    scalers_by_window : <blob>         # dict mapping window_id (0-9) -> list of scaler params per fold
    n_sessions : int                     # number of sessions included
    sessions : <blob>                  # list of session dataset names
    random_state : int                   # random state used for reproducibility
    mean_accuracy_by_window : <blob>   # dict mapping window_id (0-9) -> mean accuracy
    bic_by_window : <blob>             # dict mapping window_id (0-9) -> BIC
    cross_window_accuracy_matrix : <blob>  # nested dict: train_window -> test_window -> accuracy
    cross_window_accuracy_mean : float       # mean off-diagonal cross-window accuracy
    """

    class SessionPrediction(dj.Part):
        definition = """
        -> master
        -> Dataset
        ---
        n_samples : int                  # number of samples in the session
        mean_accuracy : float            # mean accuracy for this session
        mean_proba_left : float          # mean predicted probability for left choice
        trial : <blob>                 # trial numbers
        trial_length : <blob>          # trial progression
        proba_left : <blob>            # predicted probabilities for left choice
        accuracy : <blob>              # per-sample accuracy values
        trial_left_choice : <blob>     # ground truth left choice
        bic : <blob>                   # Bayesian Information Criterion per timestep
        model_idx : <blob>             # per-sample model/window index (0-9)
        """

    @staticmethod
    def _assign_trial_windows_10(interpolated_df):
        """Assign each sample to one of 10 equally-sized windows within each trial."""
        windowed_df = interpolated_df.sort_values(
            ["dataset", "trial", "trial_length"]
        ).copy()
        trial_index = windowed_df.groupby(["dataset", "trial"]).cumcount()
        trial_size = windowed_df.groupby(["dataset", "trial"])["trial"].transform(
            "size"
        )
        # Divide trial into 10 windows
        window_id = (trial_index * WINDOW_COUNT / trial_size).astype(int)
        window_id = np.clip(window_id, 0, WINDOW_COUNT - 1)
        windowed_df["trial_window"] = window_id
        return windowed_df

    @staticmethod
    def _compute_cross_window_accuracy_matrix(
        interpolated_df,
        coefficients_by_window,
        scalers_by_window,
        label_set,
        scale_data,
    ):
        """Compute train-window to test-window accuracy matrix using fixed weights.

        If `scale_data` is True and `scalers_by_window` contains scaler parameters for a
        given training window, reuse the averaged scaler params from the training
        window to transform each test window. Otherwise fall back to fitting a
        scaler on the test window (legacy behavior).
        """
        matrix = {}

        for train_window in range(WINDOW_COUNT):
            matrix[train_window] = {}
            coef = coefficients_by_window.get(train_window)
            if coef is None or np.isnan(np.asarray(coef)).all():
                for test_window in range(WINDOW_COUNT):
                    matrix[train_window][test_window] = np.nan
                continue

            coef_mean = np.asarray(coef).mean(axis=0)
            intercept = coef_mean[0]
            weights = coef_mean[1:]

            # Prepare averaged scaler params for this train window if available
            scaler_params = None
            if scalers_by_window is not None:
                scaler_list = scalers_by_window.get(train_window)
                if scaler_list:
                    # Filter out None entries
                    valid = [s for s in scaler_list if s is not None]
                    if valid:
                        means = np.vstack([np.asarray(s["mean"]) for s in valid])
                        scales = np.vstack([np.asarray(s["scale"]) for s in valid])
                        scaler_mean = np.mean(means, axis=0)
                        scaler_scale = np.mean(scales, axis=0)
                        scaler_params = (scaler_mean, scaler_scale)

            for test_window in range(WINDOW_COUNT):
                test_df = interpolated_df[
                    interpolated_df["trial_window"] == test_window
                ].copy()
                if test_df.empty:
                    matrix[train_window][test_window] = np.nan
                    continue

                x_test = np.asarray(test_df[label_set].values)
                y_test = test_df["trial_left_choice"].values

                if scale_data:
                    if scaler_params is not None:
                        mean_arr, scale_arr = scaler_params
                        x_test = (x_test - mean_arr) / scale_arr
                    else:
                        x_test = sklearn.preprocessing.StandardScaler().fit_transform(
                            x_test
                        )

                logits = x_test @ weights + intercept
                pred = (logits > 0).astype(int)
                matrix[train_window][test_window] = float(np.mean(pred == y_test))

        return matrix

    def make(self, key):
        """Train and store 10 LOGO models on trial progress windows."""
        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        logger.info(f"{self.__class__.__name__} population started for {key}.")

        try:
            stage_name = (ExperimentStage & key).fetch1("stage_name")
            if stage_name == "training":
                logger.info(f"Skipping training stage for {self.__class__.__name__}")
                return

            label_set = list((LabelSet.Member & key).fetch("label_key"))
            params = (ModelParams & key).fetch(as_dict=True)[0]

            sessions_list = list(
                (InclusionStatus * ExperimentMember & key & {"included": 1}).fetch(
                    "dataset"
                )
            )

            if not sessions_list:
                raise ValueError(
                    f"No valid sessions found for {self.__class__.__name__} with key {key}"
                )

            dataset_list = []
            for dataset in sessions_list:
                if len(InterpolatedTrials() & f'dataset = "{dataset}"') > 0:
                    dataset_list.append(
                        pd.DataFrame(
                            (InterpolatedTrials() & f'dataset = "{dataset}"').fetch(
                                as_dict=True
                            )[0]
                        )
                    )
                else:
                    raise ValueError(f"InterpolatedTrials missing for {dataset}")

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
                trial_choices = (
                    interpolated_df.groupby(["dataset", "trial"], as_index=False)
                    .agg({"trial_left_choice": "first"})
                    .sort_values(["dataset", "trial"])
                )
                trial_choices["trial_history"] = (
                    trial_choices.groupby("dataset")["trial_left_choice"]
                    .shift(1)
                    .fillna(0)
                )
                interpolated_df = interpolated_df.merge(
                    trial_choices[["dataset", "trial", "trial_history"]],
                    on=["dataset", "trial"],
                    how="left",
                )

            interpolated_df = self._assign_trial_windows_10(interpolated_df)

            random_state = 42
            coefficients_by_window = {}
            scalers_by_window = {}
            mean_accuracy_by_window = {}
            bic_by_window = {}
            session_prediction_by_dataset = {}

            for window_id in range(WINDOW_COUNT):
                window_df = interpolated_df[
                    interpolated_df["trial_window"] == window_id
                ].copy()

                if window_df.empty:
                    logger.warning(
                        f"No data available for window {window_id} in {self.__class__.__name__}"
                    )
                    coefficients_by_window[window_id] = np.array([[np.nan]])
                    mean_accuracy_by_window[window_id] = np.nan
                    bic_by_window[window_id] = np.nan
                    continue

                df_model, coef, scalers = regression.predict_decision(
                    df=window_df,
                    label=label_set,
                    per_mouse=True,
                    max_iter=params["max_iter"],
                    scale_data=params["scale_data"],
                    random_state=random_state,
                )

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

                coefficients_by_window[window_id] = coef
                scalers_by_window[window_id] = scalers
                mean_accuracy_by_window[window_id] = float(
                    df_model_per_trial["accuracy"].mean()
                )
                bic_by_window[window_id] = regression.compute_bic(
                    df_model_per_trial["proba_left"].values,
                    df_model_per_trial["trial_left_choice"].values,
                    n_params=len(label_set) + 1,
                )

                for dataset in df_model["dataset"].unique():
                    dataset_trials = df_model[
                        df_model["dataset"] == dataset
                    ].reset_index(drop=True)

                    bic_per_timestep = np.full(len(dataset_trials), np.nan)
                    for trial in dataset_trials["trial"].unique():
                        trial_df = dataset_trials[dataset_trials["trial"] == trial]

                        bic_per_timestep[
                            trial_df.index
                        ] = regression.compute_bic_sliding_window(
                            trial_df["proba_left"].values,
                            trial_df["trial_left_choice"].values,
                            n_params=len(label_set) + 1,
                            window_size=10,
                        )

                    session_df = pd.DataFrame(
                        {
                            "trial": dataset_trials["trial"].values,
                            "trial_length": dataset_trials["trial_length"].values,
                            "proba_left": dataset_trials["proba_left"].values,
                            "accuracy": dataset_trials["accuracy"].values,
                            "trial_left_choice": dataset_trials[
                                "trial_left_choice"
                            ].values,
                            "bic": bic_per_timestep,
                            "model_idx": np.full(len(dataset_trials), window_id),
                        }
                    )
                    dataset_entry = session_prediction_by_dataset.setdefault(
                        dataset, []
                    )
                    dataset_entry.append(session_df)

            cross_window_accuracy_matrix = self._compute_cross_window_accuracy_matrix(
                interpolated_df,
                coefficients_by_window,
                scalers_by_window,
                label_set,
                params["scale_data"],
            )
            off_diag_scores = [
                cross_window_accuracy_matrix[i][j]
                for i in range(WINDOW_COUNT)
                for j in range(WINDOW_COUNT)
                if i != j and np.isfinite(cross_window_accuracy_matrix[i][j])
            ]
            cross_window_accuracy_mean = (
                float(np.mean(off_diag_scores)) if off_diag_scores else np.nan
            )

            self.insert1(
                {
                    **key,
                    "coefficients_by_window": coefficients_by_window,
                    "scalers_by_window": scalers_by_window,
                    "n_sessions": len(sessions_list),
                    "sessions": sessions_list,
                    "random_state": random_state,
                    "mean_accuracy_by_window": mean_accuracy_by_window,
                    "bic_by_window": bic_by_window,
                    "cross_window_accuracy_matrix": cross_window_accuracy_matrix,
                    "cross_window_accuracy_mean": cross_window_accuracy_mean,
                },
                skip_duplicates=True,
            )

            if not (self & key):
                raise ValueError(
                    f"Parent row missing in {self.__class__.__name__} after insert for key {key}"
                )

            parent_key = (self & key).fetch1("KEY")
            for dataset, rows in session_prediction_by_dataset.items():
                aggregated_df = pd.concat(rows, ignore_index=True)
                aggregated_df = aggregated_df.sort_values(
                    ["trial", "trial_length", "model_idx"]
                ).reset_index(drop=True)

                child_row = {
                    **parent_key,
                    "dataset": dataset,
                    "n_samples": len(aggregated_df),
                    "mean_accuracy": float(aggregated_df["accuracy"].mean()),
                    "mean_proba_left": float(aggregated_df["proba_left"].mean()),
                    "trial": aggregated_df["trial"].to_numpy(),
                    "trial_length": aggregated_df["trial_length"].to_numpy(),
                    "proba_left": aggregated_df["proba_left"].to_numpy(),
                    "accuracy": aggregated_df["accuracy"].to_numpy(),
                    "trial_left_choice": aggregated_df["trial_left_choice"].to_numpy(),
                    "bic": aggregated_df["bic"].to_numpy(),
                    "model_idx": aggregated_df["model_idx"].to_numpy(),
                }
                self.SessionPrediction.insert1(child_row, skip_duplicates=True)
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
    threshold_uncertainty : varchar(10)
    """
    contents = [
        ("0.1",),
        ("0.2",),
        ("0.3",),
        ("0.4",),
        ("0.5",),
    ]


@schema
class DecisionPoints(dj.Computed):
    """Decision point and corresponding per-trial data."""

    definition = """
    -> PredictionModel.SessionPrediction
    -> DecisionThreshold
    ---
    trial: <blob>                 # trial corresponding to the timestamp
    proba_left: <blob>            # pred proba of the regression on decision side
    aperture: <blob>              # occlusion size for the corresponding trial
    trial_left_choice: <blob>     # ground truth on the decision side
    trial_rewarded: <blob>        # 1 if trial was rewarded, else 0
    trial_length: <blob>          # length of the trial at which decision was made
    x: <blob>                     # x position of the decision point in the trial
    y: <blob>                     # y position of the decision point in the trial
    """

    def make(self, key):
        """Compute decision points from model predictions and trials."""
        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        logger.info(f"{self.__class__.__name__} population started for {key}.")

        try:
            # Only compute decision points for session included in the analysis
            if not (InclusionStatus() & key & {"included": 1}):
                return

            threshold_uncertainty = float(
                (DecisionThreshold & key).fetch1("threshold_uncertainty")
            )

            predictions_df = pd.DataFrame(
                (PredictionModel.SessionPrediction & key).fetch(
                    "dataset", "trial", "proba_left", "trial_length", as_dict=True
                )[0]
            )

            trial_df = pd.DataFrame(
                (InterpolatedTrials() & key).fetch(
                    "dataset",
                    "trial_left_choice",
                    "x",
                    "y",
                    "trial_rewarded",
                    "aperture",
                    "trial_length",
                    "trial",
                    as_dict=True,
                )[0]
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


@schema
class DecisionPoints10Windows(dj.Computed):
    """Decision points computed from 10-window model predictions."""

    definition = """
    -> PredictionModel10Windows.SessionPrediction
    -> DecisionThreshold
    ---
    trial: <blob>                 # trial corresponding to the timestamp
    proba_left: <blob>            # pred proba of the regression on decision side
    aperture: <blob>              # occlusion size for the corresponding trial
    trial_left_choice: <blob>     # ground truth on the decision side
    trial_rewarded: <blob>        # 1 if trial was rewarded, else 0
    trial_length: <blob>          # length of the trial at which decision was made
    x: <blob>                     # x position of the decision point in the trial
    y: <blob>                     # y position of the decision point in the trial
    """

    def make(self, key):
        """Compute decision points from 10-window model predictions and trials."""
        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        logger.info(f"{self.__class__.__name__} population started for {key}.")

        try:
            # Only compute decision points for sessions included in the analysis
            if not (InclusionStatus() & key & {"included": 1}):
                return

            threshold_uncertainty = float(
                (DecisionThreshold & key).fetch1("threshold_uncertainty")
            )

            trial, proba_left, trial_length = (
                PredictionModel10Windows.SessionPrediction & key
            ).fetch1("trial", "proba_left", "trial_length")
            predictions_df = pd.DataFrame(
                {
                    "dataset": key["dataset"],
                    "trial": trial,
                    "proba_left": proba_left,
                    "trial_length": trial_length,
                }
            )

            trial_df = pd.DataFrame(
                (InterpolatedTrials() & key).fetch(
                    "dataset",
                    "trial_left_choice",
                    "x",
                    "y",
                    "trial_rewarded",
                    "aperture",
                    "trial_length",
                    "trial",
                    as_dict=True,
                )[0]
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

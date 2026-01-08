"""
Schemes related to the regression model and decision point analysis.
"""

import datajoint as dj
import pandas as pd

from vr4mice.analysis import regression

from vr4mice.schema.vr4mice import Dataset
from vr4mice.schema.session_metrics import TrialMetrics
from vr4mice.schema.interpolated_trajectories import InterpolatedTrials

from vr4mice.utils.logger import Logger

from vr4mice.utils.schema_config import get_schema

schema_name = "decision"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()


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

    def make(self, key):
        try:
            trial_df = (TrialMetrics() * (Dataset() & key)).fetch(as_dict=True)
            trial_df = pd.concat([pd.DataFrame(x) for x in trial_df])
            trial_df["aperture"] = trial_df.aperture.round(2)

            # Exclude sessions that were not in the list
            from vr4mice.analysis.utils import apply_inclusion_criteria

            if trial_df["session_label"].iloc[0] == "ar_discrim_occluders":
                trial_df, _ = apply_inclusion_criteria(
                    trial_df, task_type="dual_occluder"
                )

                if not trial_df.empty:
                    self.insert1({**key, "dual_occl": 1, "multi_occl": 0})
                else:
                    self.insert1({**key, "dual_occl": 0, "multi_occl": 0})
            elif trial_df["session_label"].iloc[0] == "ar_discrim_5_occluders":
                trial_df, _ = apply_inclusion_criteria(
                    trial_df, task_type="multi_occluder"
                )

                if not trial_df.empty:
                    self.insert1({**key, "dual_occl": 0, "multi_occl": 1})
                else:
                    self.insert1({**key, "dual_occl": 0, "multi_occl": 0})
            else:
                logger.warning(
                    f"Unknown session label {trial_df['session_label'].iloc[0]} for key {key}"
                )
                return
        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None


@schema
class LabelSet(dj.Lookup):
    definition = """
    label_id : int          # unique ID for the label set
    ---
    label_name : varchar(32)   # name of the label set
    labels : longblob       # the actual y-vector
    """


@schema
class ModelParams(dj.Lookup):
    definition = """
    param_id : int          # unique ID for hyperparam combo
    ---
    max_iter : int          # maximum number of iterations for logistic regression
    scale_data : bool       # whether to scale data before training
    """


@schema
class TaskType(dj.Lookup):
    definition = """
    task_type : varchar(32)      # type of task (e.g., dual_occl, multi_occl)
    ---
    description : varchar(255)   # description of the task type
    """


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
        proba_left : longblob          # predicted probabilities for left choice
        accuracy : longblob            # per-trial accuracy values
        """

    def make(self, key):
        try:
            from vr4mice.schema.vr4mice import Dataset

            # Get label set and model params
            label_set = (LabelSet & key).fetch1("labels")
            params = (ModelParams & key).fetch1()
            task_type = (TaskType & key).fetch1("task_type")

            sessions_list = list((ValidGroup & f"{task_type}=1").fetch("dataset"))

            # This takes a while to fetch because we need to fetch data from all sessions
            dataset_list = []
            for d in sessions_list:
                try:
                    if len(InterpolatedTrials() & f'dataset = "{d}"') > 0:
                        dataset_list.append(
                            pd.DataFrame(
                                (InterpolatedTrials() & f'dataset = "{d}"').fetch(
                                    as_dict=True
                                )[0]
                            )
                        )
                    else:
                        print("Dataset missing")
                except Exception as err:
                    print(err, " Dataset missing")

            interpolated_df = pd.concat(dataset_list)
            interpolated_df["mouse_name"] = interpolated_df.dataset.str.split("_").str[
                0
            ]
            interpolated_df["aperture"] = interpolated_df["aperture"].astype(float)

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

            self.insert1(
                {
                    **key,
                    "coefficients": coef,
                    "n_sessions": len(sessions_list),
                    "sessions": sessions_list,
                    "random_state": random_state,
                }
            )

            # Insert per-session predictions
            for dataset in df_model["dataset"].unique():
                dataset_trials = df_model[df_model["dataset"] == dataset]
                self.SessionPrediction.insert1(
                    {
                        **key,
                        "dataset": dataset,
                        "n_samples": len(dataset_trials),
                        "mean_accuracy": float(dataset_trials["accuracy"].mean()),
                        "mean_proba_left": float(dataset_trials["proba_left"].mean()),
                        "trial": dataset_trials["trial"].values,
                        "proba_left": dataset_trials["proba_left"].values,
                        "accuracy": dataset_trials["accuracy"].values,
                    }
                )
        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None


@schema
class DecisionPoints(dj.Computed):
    """Decision point and corresponding per-trial data."""

    definition = """
    -> PredictionModel
    -> InterpolatedTrials
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
        #try:
        predictions_df = pd.DataFrame(
            (PredictionModel.SessionPrediction & key).fetch(
                "trial", "proba_left", as_dict=True
            )[0]
        )
        
        trial_df = pd.DataFrame((InterpolatedTrials() & key).fetch(
            "dataset", "trial_left_choice", 
            "x", "y", "trial_rewarded", 
            "aperture", "trial_length", 
            as_dict=True)[0])

        merged_df = pd.merge(predictions_df, trial_df, left_index=True, right_index=True)
        
        decision_points = regression.find_decision_point(
            merged_df, threshold_uncertainty=0.3
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
            
        # except Exception as err:
        #     logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
        #     return None

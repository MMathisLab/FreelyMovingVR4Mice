# Architecture & Tables

## Quick Intro & Resources to DataJoint

DataJoint is an open-source data management framework designed for scientific workflows, especially in neuroscience and experimental biology. It provides a relational data model and tools for building, querying, and maintaining complex data pipelines. DataJoint enables modular, reproducible, scalable, and collaborative data analysis by organizing data into well-defined tables and automating dependencies between processing steps.

> **DataJoint Table Types**
> 
> DataJoint organizes data into several table types, each serving a specific role in a scientific data pipeline:
> 
> - **Manual Tables (`dj.Manual`)**: Populated by users or external systems. Used for raw data, experiment metadata, or any information entered manually.
> - **Imported Tables (`dj.Imported`)**: Populated by automated scripts that import data from external sources or files. Used for data acquired from instruments or external analysis.
> - **Computed Tables (`dj.Computed`)**: Populated by automated computations based on upstream tables. Used for analysis, processing, and derived results.
> - **Lookup Tables (`dj.Lookup`)**: Contain reference information, such as lists of hardware, experimental conditions, or other constants.

**Useful Links:**
- [DataJoint Documentation](https://docs.datajoint.org/)
- [DataJoint GitHub](https://github.com/datajoint/datajoint)

**Related VR4Mice docs:**
- {ref}`Setup & Usage <sec:install-dj-pipeline>`
- {ref}`Deploy the DataJoint database locally <sec:import-sql-dump>`
- `docs/software/data_import_export.md`

## Repository Structure and Roles
### Key components

1. **Graphical User Interface (GUI)** for metadata and data transfer.
2. **VR4mice DataJoint pipeline** including table definitions, as well as external schemas for experiments and mice.
3. **Data fetching and population.**
4. **System/Docker**: Uses Docker Compose for deployment. *Ensure Docker Compose is available (`docker compose` or `docker-compose`) and your user is in the Docker group.*

### Codebase overview

1. The **`base/base_min_schemas/`** directory contains minimal `exp` and `mice` schema definitions needed for GUI dropdowns and basic metadata.
2. The **`Dockerfile`** and **`docker/entrypoint.sh`** build the client image used by `docker-compose.yml`.
3. The **`gui_transfer/`** folder contains all GUI-related information. Only this folder, plus Python 3 and PyQt5, are needed to build the GUI on a rig computer. For dropdown menu paths and rig `config.json` setup, see {ref}`GUI dropdown menu and rig setup <gui-dropdown-menu>`.
4. The **`run.py`** script is the main CLI entrypoint for running pipeline modes (populate, analysis, dlc, etc.).
5. The **`cron_scenario.py`** script runs the full pipeline with per-step logging (used by cron). See {ref}`Cron and Docker operations <cron-and-docker>` for wrapper scripts, crontab setup, and compose project naming.
6. The **`quick_start.sh`** script interactively configures `.env`/`env.py` and starts containers.
7. The **`vr4mice/`** folder contains the core of the pipeline, including `vr4mice` schema (table definitions) and actions.
8. The **`Makefile`** provides shortcuts for Docker and common commands.
9. The **`docker-compose.yml`** file defines the database and client services and volume mounts.

![Untitled presentation(4)](https://user-images.githubusercontent.com/43879378/234044336-e7693e02-e8de-4000-9dd0-1716a80002db.jpg)

## Tables in the `vr4mice/schema` Pipeline

Each file under `dj_pipeline/vr4mice/schema/` has a module-level docstring, and each top-level DataJoint table class has a class-level docstring describing its role (nested `dj.Part` tables may not). The summaries below mirror those docstrings.

```{image} ../../docs/images/vr4mice-erd.png
:alt: vr4mice_erd
:class: bg-primary mb-1
:align: center
```

### `base.py`

*Base schema linking datasets to shared experiment metadata.*

```python
class Base(dj.Computed)
```
**Depends on:** `vr4mice.Dataset`  
Links together `Dataset` with base `Mouse` and `Exp` schemas.

### `vr4mice.py`

*Core VR4Mice schema tables for datasets, metadata, and raw signals.*

```python
class Camera(dj.Lookup)
```
Camera definition table; to be updated if a new camera name is added.

```python
class Dataset(dj.Manual)
```
Stores dataset names representing VR experiments; keeps raw pickle and npy files (`mouse_name_doe_attempt` format).

```python
class FailedSession(dj.Manual)
```
Tracks dataset/table pairs that failed during populate/compute.

```python
class Labels(dj.Lookup)
```
Stores custom group labels assigned to datasets.

```python
class Groups(dj.Manual)
```
Links datasets to custom `Labels` entries.

```python
class Labs(dj.Lookup)
```
Stores collaborating lab identifiers.

```python
class Collab(dj.Computed)
```
Links each dataset to a collaborating lab.

```python
class Video(dj.Manual)
```
Stores raw video file metadata, timestamp files, and paths on the rig PC.

```python
class ModelName(dj.Lookup)
```
Stores DLC model names applied to video analysis; can be extended for new model types.

```python
class DLC(dj.Manual)
```
Stores local paths to keypoints and processed keypoints files.

```python
class MouseState(dj.Manual)
```
Stores mouse game-related position and events; fetched from the teensy output pickle file.

```python
class State(dj.Manual)
```
**Depends on:** `vr4mice.MouseState`  
Stores trial-related information; fetched from the teensy output pickle file.

```python
class Metadata(dj.Manual)
```
Stores Unity parameters and session metadata; fetched from the teensy output pickle file.

```python
class SignalsPhotodiode(dj.Computed)
```
Stores photodiode and generated sync signals from the PROC file.

```python
class GuiParams(dj.Manual)
```
Stores Unity game parameters fetched from the teensy output pickle file.

```python
class TrainingPhaseType(dj.Lookup)
```
Stores training phase categories used to classify datasets.

```python
class DatasetType(dj.Computed)
```
**Depends on:** `vr4mice.Metadata`  
Assigns each dataset to a training phase based on metadata and state.

```python
class Box(dj.Manual)
```
**Depends on:** `vr4mice.Metadata`  
Stores box positions; fetched from the teensy output pickle file.

```python
class Object(dj.Lookup)
```
Stores target and distractor object names used in the game.

### `base_analysis.py`

*Analysis schema tables built on top of core VR4Mice datasets.*

```python
class DataFrame(dj.Computed)
```
**Depends on:** `vr4mice.Dataset`  
Hosts the main per-step analysis dataframe (trial data, position, velocity, choices, rewards, and behavioral metrics). Populated via `create_data_frame(key)`.

```python
class BoxDataFrame(dj.Computed)
```
**Depends on:** `DataFrame`  
Stores per-trial report and target box coordinates derived from `DataFrame`.

```python
class SummaryPlots(dj.Computed)
```
**Depends on:** `vr4mice.Dataset`, `DataFrame`, `BoxDataFrame`  
Stores paths to generated per-session summary plot figures.

```python
class GitCommit(dj.Computed)
```
**Depends on:** `DataFrame`  
Stores git commit hash and changed files for analysis reproducibility.

### `dlc.py`

*DLC-related schema tables for keypoints and derived kinematics.*

```python
class DLCProcessor(dj.Imported)
```
**Depends on:** `vr4mice.DLC`  
Imports processed DLC outputs from the PROC npy file.

```python
class DLCKptsDf(dj.Computed)
```
**Depends on:** `vr4mice.DLC`  
All available raw DLC keypoints with likelihood.

```python
class SyncDLCKptsDf(dj.Computed)
```
**Depends on:** `DLCKptsDf`  
Filtered and game-synchronized DLC keypoints.

```python
class OfflineKinematics(dj.Computed)
```
**Depends on:** `SyncDLCKptsDf`  
Stores mouse body kinematics computed offline from synchronized DLC keypoints.

### `interpolated_trajectories.py`

*Interpolated trajectory schema used for downstream analysis tables.*

```python
class InterpolatedTrials(dj.Computed)
```
**Depends on:** `base_analysis.DataFrame`  
Stores J-shaped interpolated per-trial trajectories and kinematics.

```python
class MeanXYTrajectory(dj.Computed)
```
**Depends on:** `InterpolatedTrials`  
Stores mean x/y trajectories across trials for each aperture.

```python
class YBinnedXYTrajectory(dj.Computed)
```
**Depends on:** `InterpolatedTrials`  
Stores y-binned mean trajectories for each aperture.

```python
class MeanVelocities(dj.Computed)
```
**Depends on:** `InterpolatedTrials`  
Stores mean velocities across trials for each aperture and trial length.

### `latency_tests.py`

*Latency testing schema for photodiode and frame timing analysis.*

```python
class SignalsPhotodiodeAligned(dj.Computed)
```
**Depends on:** `vr4mice.SignalsPhotodiode`  
Stores interpolated and aligned photodiode and generated sync signals.

```python
class AllLatencies(dj.Computed)
```
**Depends on:** `SignalsPhotodiodeAligned`  
Stores per-session latency between generated and photodiode signal edges.

### `session_metrics.py`

*Session-level and trial-level summary metrics schema.*

```python
class SessionMetrics(dj.Computed)
```
**Depends on:** `vr4mice.Dataset` (populated from `base_analysis.DataFrame`)  
Stores session-level summary metrics computed from `base_analysis.DataFrame`.

```python
class TrialMetrics(dj.Computed)
```
**Depends on:** `base_analysis.DataFrame`  
Stores per-trial summary metrics derived from the `DataFrame` table.

### `decision.py`

*Decision analysis schema for regression models and decision points.*

```python
class SessionLabel(dj.Lookup)
```
Maps session labels to experiment set and stage.

```python
class ExperimentSet(dj.Lookup)
```
Stores experiment set names and descriptions.

```python
class ExperimentStage(dj.Lookup)
```
Stores experiment stage names and descriptions.

```python
class ExperimentMember(dj.Imported)
```
**Depends on:** `vr4mice.Dataset`  
Links each dataset to an experiment set, stage, and session label.

```python
class InclusionStatus(dj.Computed)
```
**Depends on:** `ExperimentMember`  
Inclusion status per dataset and experiment set role.

```python
class Label(dj.Lookup)
```
Stores regression feature names used in decision analysis.

```python
class LabelSet(dj.Lookup)
```
Stores named sets of regression labels for model training.

```python
class ModelParams(dj.Lookup)
```
Stores logistic regression hyperparameter combinations.

```python
class PredictionModel(dj.Computed)
```
**Depends on:** `LabelSet`, `ModelParams`, `ExperimentSet`, `ExperimentStage`  
Trains logistic regression model per mouse using LOGO cross-validation.

```python
class PredictionModel10Windows(dj.Computed)
```
**Depends on:** `LabelSet`, `ModelParams`, `ExperimentSet`, `ExperimentStage`  
Trains LOGO regression models on 10 equally-spaced trial progress windows.

```python
class DecisionThreshold(dj.Lookup)
```
Lookup table for different uncertainty thresholds to define decision points.

```python
class DecisionPoints(dj.Computed)
```
**Depends on:** `PredictionModel.SessionPrediction`, `DecisionThreshold`  
Decision point and corresponding per-trial data.

```python
class DecisionPoints10Windows(dj.Computed)
```
**Depends on:** `PredictionModel10Windows.SessionPrediction`, `DecisionThreshold`  
Decision points computed from 10-window model predictions.

### `inputs_videos.py`

*Video input schema for sync/crop/align operations on session recordings.*

```python
class RawVideo(dj.Imported)
```
**Depends on:** `vr4mice.Dataset`  
Stores the raw OBS recording path for a dataset.

```python
class ProcessedVideo(dj.Computed)
```
**Depends on:** `RawVideo`  
Stores cropped/truncated OBS videos and ROI metadata.

```python
class VideoSyncSignal(dj.Computed)
```
**Depends on:** `ProcessedVideo`  
Extracts the binary sync trace from the sync ROI video.

```python
class AlignedVideoFrame(dj.Computed)
```
**Depends on:** `VideoSyncSignal`, `vr4mice.State`  
Aligns game steps to video frames using photodiode when available; stores QA metrics.
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
- `docs/software/install_dj_pipeline.md`
- `docs/software/quickstart_local_dump.md`
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
3. The **`gui_transfer/`** folder contains all GUI-related information. Only this folder, plus Python 3 and PyQt5, are needed to build the GUI on a rig computer.
4. The **`run.py`** script is the main CLI entrypoint for running pipeline modes (populate, analysis, dlc, etc.).
5. The **`cron_scenario.py`** script runs the full pipeline with per-step logging (used by cron).
6. The **`quick_start.sh`** script interactively configures `.env`/`env.py` and starts containers.
7. The **`vr4mice/`** folder contains the core of the pipeline, including `vr4mice` schema (table definitions) and actions.
8. The **`Makefile`** provides shortcuts for Docker and common commands.
9. The **`docker-compose.yml`** file defines the database and client services and volume mounts.

![Untitled presentation(4)](https://user-images.githubusercontent.com/43879378/234044336-e7693e02-e8de-4000-9dd0-1716a80002db.jpg)

## Tables in the `vr4mice/schema` Pipeline

```{image} ../../docs/images/vr4mice-erd.png
:alt: vr4mice_erd
:class: bg-primary mb-1
:align: center
```

### `base.py`

```python
class Base(dj.Computed)
```
Core experiment computed table.

### `base_analysis.py`

```python
class DataFrame(dj.Computed)
```
**Depends on:** `vr4mice.Dataset`  
Main analysis dataframe including trial data, position (x,y), velocity, acceleration, choices, rewards, and behavioral metrics. Runs `create_data_frame(key)` to get the data into a `pd.DataFrame`.

```python
class BoxDataFrame(dj.Computed)
```
**Depends on:** `DataFrame`  
Box and reward zone coordinates, angles, and boundaries for left/right/target boxes using `get_box_df()`.

```python
class SummaryPlots(dj.Computed)
```
**Depends on:** `vr4mice.Dataset`, `DataFrame`, `BoxDataFrame`  
Generates and stores summary plots for each dataset using `vr4mice_summary_plots()`.

```python
class GitCommit(dj.Computed)
```
**Depends on:** `DataFrame`  
Git commit hash and changed files for reproducibility tracking.

### `dlc.py`

```python
class DLCProcessor(dj.Imported)
```
**Depends on:** `vr4mice.DLC`  
**Imports:** DeepLabCut pose estimation results from external files.

```python
class DLCKptsDf(dj.Computed)
```
**Depends on:** `DLCProcessor`  
Processes DLC keypoints into structured dataframes.

```python
class SyncDLCKptsDf(dj.Computed)
```
**Depends on:** `DLCKptsDf`  
Synchronizes DLC keypoints with experiment timing and events.

```python
class OfflineKinematics(dj.Computed)
```
**Depends on:** `SyncDLCKptsDf`  
Offline kinematics analysis from synchronized DLC pose data.

### `interpolated_trajectories.py`

```python
class InterpolatedTrials(dj.Computed)
```
Interpolated trial trajectories for smooth motion analysis.

```python
class MeanXYTrajectory(dj.Computed)
```
**Depends on:** `InterpolatedTrials`  
Mean XY trajectories averaged across multiple trials.

```python
class YBinnedXYTrajectory(dj.Computed)
```
**Depends on:** `InterpolatedTrials`  
Y-axis binned XY trajectories for spatial analysis.

```python
class MeanVelocities(dj.Computed)
```
**Depends on:** `InterpolatedTrials`  
Mean velocities computed from interpolated trial data.

### `latency_tests.py`

```python
class SignalsPhotodiodeAligned(dj.Computed)
```
**Depends on:** `vr4mice.SignalsPhotodiode`  
Signals aligned to photodiode events for timing analysis.

```python
class AllLatencies(dj.Computed)
```
**Depends on:** `SignalsPhotodiodeAligned`  
All measured latencies from photodiode signal alignment.

### `session_metrics.py`

```python
class SessionMetrics(dj.Computed)
```
Session-level performance metrics and statistics.

```python
class TrialMetrics(dj.Computed)
```
Individual trial-level metrics and behavioral measures.

### `vr4mice.py`

```python
class Camera(dj.Lookup)
```
**Reference table:** Camera hardware definitions and configurations.

```python
class Dataset(dj.Manual)
```
**Manual entry:** Dataset metadata containing most raw experimental data.

```python
class FailedSession(dj.Manual)
```
**Manual entry:** Tracks failed sessions and error logging; used as a skip list to prevent repeated failures.

```python
class Labels(dj.Lookup)
```
**Reference table:** Label definitions for experimental conditions.

```python
class Groups(dj.Manual)
```
**Manual entry:** Experimental group assignments and metadata.

```python
class Labs(dj.Lookup)
```
**Reference table:** Laboratory information and configurations.

```python
class Collab(dj.Computed)
```
Collaboration and sharing information.

```python
class Video(dj.Manual)
```
**Manual entry:** Video file metadata and paths.

```python
class ModelName(dj.Lookup)
```
**Reference table:** Model name definitions for analysis pipelines.

```python
class DLC(dj.Manual)
```
**Manual entry:** DeepLabCut model metadata and configurations.

```python
class MouseState(dj.Manual)
```
**Manual entry:** Mouse behavioral state information.

```python
class State(dj.Manual)
```
**Manual entry:** General experimental state information.

```python
class Metadata(dj.Manual)
```
**Manual entry:** General experimental metadata.

```python
class SignalsPhotodiode(dj.Computed)
```
Photodiode signal processing and timing data.

```python
class GuiParams(dj.Manual)
```
**Manual entry:** GUI parameter settings and configurations.

```python
class TrainingPhaseType(dj.Lookup)
```
**Reference table:** Training phase type definitions.

```python
class DatasetType(dj.Computed)
```
Dataset type classification and information.

```python
class Box(dj.Manual)
```
**Manual entry:** Experimental box metadata and configurations.

```python
class Object(dj.Lookup)
```
**Reference table:** Object definitions used in experiments.
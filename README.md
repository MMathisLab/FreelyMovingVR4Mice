# FreelyMovingVR4Mice

<p align="center">
  <img src="docs/images/paper_videos/video_s1.gif" width="90%" alt="Supplementary Video S1" />
</p>

FreelyMovingVR4Mice is the MLAI lab codebase for running the freely moving VR mouse rig. It brings together the Python control stack, task scripts, DeepLabCut integration, Teensy hardware control, Unity assets, and the documentation needed to build, calibrate, and run experiments.

Happy experimenting 🙂

## What is in this repository 🔎

- `teensyexp/`: the main Python package that provides the `vr4mice` GUI, task orchestration, socket helpers, and experiment control logic.
- `mouse_task/`: task definitions and experiment scripts, including detection and discrimination tasks, DLC processors, latency tests, and the bundled Unity build.
- `docs/`: the user guide for hardware build, calibration, software setup, Unity workflows, training protocols, and the migration guide.
- `audio/`: audio analysis helpers.
- `tests/`: unit, integration, and golden-baseline tests for the pipeline and helper functions.
- `Blender_objects/` and `docs/stl_files/`: rig and hardware assets.

## Quick start 🚀

The main package is installed from the repository root:

```bash
conda create -n vr4mice python=3.10.12
conda activate vr4mice
pip install .
```

Then launch the GUI:

```bash
vr4mice
```

For development, use editable mode instead:

```bash
pip install -e .
```

You are all set to start 😄

## Important links 🔗

- [Project documentation 📚](https://mmathislab.github.io/FreelyMovingVR4Mice)
- [Public data release (Zenodo) 🗂️](https://zenodo.org/records/21099082)
- [Installation guide ⚙️](docs/software_installation/installation.md)
- [Run a session ▶️](docs/software_installation/run_a_session.md)
- [Config file setup 🧩](docs/software_installation/config_file_setup.md)
- [Install DeepLabCut-live-GUI 🐭](https://github.com/DeepLabCut/DeepLabCut-live-GUI)
- [User guide 🧭](docs/user_guide.md)
- [VR4Mice overview 🕶️](docs/vr4mice_overview.md)
- [Hardware build and calibration docs 🔧](docs/hardware/building_the_box.md)
- [Software package docs 🧪](docs/software_package/active_sensing_task.md)

## Hardware and software requirements 🛠️

- Python 3.10.12
- Windows 10 or newer
- Unity 2022.3.15f1
- Teensy 4.0 or newer
- A GPU-capable machine for DeepLabCut-based tracking

The recommended setup uses two separate environments:

- `vr4mice` for the main control GUI and task runner
- `dlclive_gui` for DeepLabCut-live-GUI and real-time pose extraction

## Citation

Please cite our work is you use code or ideas from this project! Thank you!

We appreciate your support 😊

Célia Benquet*, Thomas Sainsbury*, Léo Bruneau, Yang Lin, Chenchen Cai, Mariia Popova, Kayla Ponder, Lydia Ntanavara, Rachel Froebe, Zheng Tan, Paul Fahey, Katrin Franke, Luis M. Franco, Keaton Jones, Yizhou Chen, Reece Keller, Xaq Pitkow, Cristopher M. Niell, Andreas S. Tolias, Mackenzie Weygandt Mathis. [Visual uncertainty and task demands shape active sensing strategies in mice.](https://www.cell.com/current-biology/fulltext/S0960-9822(26)00722-0?) Current Biology 20 July 2026. DOI: 10.1016/j.cub.2026.06.011

"""Configuration helpers for the Unity Active Sensing RL task.

This module defines a typed Pydantic model (``ActiveSensingConfig``) that
captures the parameters required to launch and control the Unity environment,
and a convenience loader (``load_config``) that merges defaults, named presets
from a YAML file, and caller-provided overrides.
"""

import yaml
from pathlib import Path
from typing import List, Optional, Any
from pydantic import BaseModel, Field
from pydantic import ConfigDict, field_validator


class ActiveSensingConfig(BaseModel):
    """Typed config object used to start the Unity task.

    The fields mirror keys in ``rl_task/config/rl_experiments.yaml`` and are
    passed to the underlying task facade. See that file for typical presets.
    """
    # Core runtime params (required)
    env_path: Optional[str] = None
    teensy: Any
    fps: int
    base_port: int
    worker_id: int
    batchmode: bool
    save_data: bool

    monitor: Optional[str] = None
    write_video: bool = False
    session_label: List[str] = Field(default_factory=lambda: ["rl_task"])
    epochs: List[int] = Field(default_factory=lambda: [250])
    epoch_labels: List[str] = Field(default_factory=lambda: ["dual_teardrop"])
    config_file_path: Optional[str] = None
    reward_size: float = 100.0
    cropped_image: List[int] = Field(default_factory=lambda: [0, 530, 0, 510])
    unity_arena_size: List[float] = Field(default_factory=lambda: [-9, 9, -10, -2])
    r_report_box: List[float] = Field(default_factory=lambda: [7, 10, -3.5, -1])
    l_report_box: List[float] = Field(default_factory=lambda: [-10, -7, -3.5, -1])
    start_box: List[float] = Field(default_factory=lambda: [-4, 4, -9, -5, 90])
    rotate_camera: float = 90.0
    prob_obj_on_left: float = 0.5
    prob_block_coherence: float = 0.5
    mouse_report_delay: float = 0.0
    slit_size: List[float] = Field(default_factory=lambda: [4.0, 4.0, 1])
    slit_depth: float = 0.02
    target_selection: float = 13.0
    distractor_selection: float = 6.0
    occlusion_type: float = 0.0
    camera_type: float = 1.0
    target_spread: float = 3.0
    target_rotation: float = 15.0
    target_size: float = 2.0
    target_height: float = 3.0
    block_length: float = 1.0
    start_box_delay: float = 0.25
    velocity_threshold: float = 20.0
    distractor: float = 1.0
    grey_screen_active: float = 0.0
    target_distance: float = 4.0
    use_dlc: bool = False
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra='forbid',
    )

    @field_validator('prob_obj_on_left', 'prob_block_coherence')
    @classmethod
    def _prob_in_unit_interval(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("probabilities must be in [0, 1]")
        return v

    def as_kwargs(self) -> dict:
        """Return the configuration as a plain ``dict`` for easy unpacking."""
        return self.model_dump()


def load_config(preset_name: str, **overrides) -> ActiveSensingConfig:
    """Load, merge, and validate a configuration preset.

    Args:
        preset_name: Key under ``presets`` in the YAML file.
        **overrides: Arbitrary key-value pairs that take precedence.

    Returns:
        ActiveSensingConfig: The merged and validated configuration.
    """
    # Retrieve .yaml config file in same folder
    yaml_path = Path(__file__).resolve().parent / "rl_experiments.yaml"
    with open(yaml_path, "r") as f:
        cfg = yaml.safe_load(f) or {}

    base = cfg.get("defaults", {}) or {}
    presets = cfg.get("presets", {}) or {}
    if preset_name not in presets:
        raise KeyError(
            f"Preset '{preset_name}' not found in {yaml_path}. "
            f"Available: {list(presets)}"
        )

    merged = {**base, **presets[preset_name], **overrides}
    return ActiveSensingConfig(**merged)

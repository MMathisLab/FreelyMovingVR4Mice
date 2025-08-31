import yaml
from typing import List, Optional
from pydantic import BaseModel, Field


class ActiveSensingConfig(BaseModel):
    env_path: str | None
    teensy: object
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

    def as_kwargs(self) -> dict:
        return self.model_dump()


def load_config(preset_name: str, yaml_path: str, **overrides) -> ActiveSensingConfig:
    with open(yaml_path, "r") as f:
        cfg = yaml.safe_load(f)

    base = cfg.get("defaults", {})
    presets = cfg.get("presets", {})
    if preset_name not in presets:
        raise KeyError(
            f"Preset '{preset_name}' not found in {yaml_path}. Available: {list(presets)}"
        )

    merged = {**base, **presets[preset_name], **overrides}
    return ActiveSensingConfig(**merged)

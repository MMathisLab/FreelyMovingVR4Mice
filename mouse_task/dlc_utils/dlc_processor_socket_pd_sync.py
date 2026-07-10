"""Sync photodiode processor that reuses the shared DLC/socket behavior."""

import importlib.util
import sys
from pathlib import Path
import time
from typing import Any, Dict, Optional
import logging
import warnings
import json
import pickle

import pandas as pd
import numpy as np
from numpy.typing import NDArray

from dlclivegui.processors import PROCESSOR_REGISTRY, register_processor  # type: ignore[import-not-found]

try:
    from dlc_utils.dlc_processor_socket_pd import dlc_inference_w_pd
except ModuleNotFoundError:
    _local_path = Path(__file__).with_name("dlc_processor_socket_pd.py")
    _local_name = "dlclivegui_plugins.local_dlc_processor_socket_pd"
    _spec = importlib.util.spec_from_file_location(_local_name, _local_path)
    if _spec is None or _spec.loader is None:
        raise ImportError(f"Could not import dlc_inference_w_pd from {_local_path}")
    _module = sys.modules.get(_local_name)
    if _module is None:
        _module = importlib.util.module_from_spec(_spec)
        sys.modules[_local_name] = _module
        _spec.loader.exec_module(_module)
    dlc_inference_w_pd = _module.dlc_inference_w_pd

import_issues = None
try:
    from latency_tests.Teensy_latency.TeensyLatencySync import TeensyLatencySync
except ModuleNotFoundError as e:
    TeensyLatencySync = None
    import_issues = e

PROCESSOR_REGISTRY.pop("dlc_inference_w_pd_sync", None)
logger = logging.getLogger(__name__)

@register_processor
class dlc_inference_w_pd_sync(dlc_inference_w_pd):
    PROCESSOR_NAME = "SocketProcessorWithPDSync"
    HEAD_CONF_THRESHOLD = 0.01
    PROCESSOR_DESCRIPTION = "Photodiode processor with Teensy sync timing capture."
    PROCESSOR_BUILD_IN_WORKER = True # legacy initialization ensures compatibility with old dlclivegui processors
    PROCESSOR_PARAMS = {
        "com": {
            "type": "str",
            "default": "COM3",
            "description": "Serial port used for Teensy.",
        },
        "baudrate": {
            "type": "int",
            "default": 9600,
            "description": "Teensy serial baudrate.",
        },
        "signal_delay": {
            "type": "float",
            "default": 10,
            "description": "Delay in seconds before TTL signal starts.",
        },
        "signal_type": {
            "type": "str",
            "default": "pulse_geo",
            "description": "Signal mode: pulse, pulse_geo, sin, or flip.",
        },
        "freq": {
            "type": "float",
            "default": 5,
            "description": "Signal frequency in Hz.",
        },
        "use_teensy": {
            "type": "bool",
            "default": True,
            "description": "Enable Teensy photodiode acquisition.",
        },
    }

    def __init__(
        self,
        com="COM3",
        baudrate=9600,
        signal_delay=10,
        signal_type="pulse_geo",
        freq=5,
        use_teensy=1,
    ):
        self.save_path: Optional[Path] = None
        ###
        self._legacy_recording_active = False
        self._legacy_poses = []
        self._legacy_pose_times = []
        self._legacy_frame_times = []

        
        try:
            super().__init__(
                com=com,
                baudrate=baudrate,
                signal_delay=signal_delay,
                signal_type=signal_type,
                freq=freq,
                use_teensy=use_teensy,
            )
            logger.info(
                f"Listener status: {self.listener._listener._socket.getsockname()} with authkey: {self.authkey}"
            )
        except Exception as e:
            self.stop(save=False)
            raise RuntimeError(
                f"Failed to initialize dlc_inference_w_pd_sync: {e}."
            ) from e
    
    def process(self, pose: NDArray[np.float64], **kwargs: Any) -> NDArray[np.float64]:
        processed_pose = super().process(pose, **kwargs)
        if getattr(self, "_legacy_recording_active", False):
            try:
                # NOTE from @C-Achard to @CeliaBenquet: 
                # I am casting pose as float32 to mitigate 
                # potential issues with RAM usage over time.
                # If this is a problem, change it back to float64.
                self._legacy_poses.append(np.asarray(pose, dtype=np.float32).copy())
                self._legacy_pose_times.append(time.time())
                self._legacy_frame_times.append(kwargs.get("frame_time", time.time()))
            except Exception:
                logger.exception("Failed to buffer pose for legacy DLC save")
        return processed_pose
    
    def _create_teensy(self, com, baudrate):
        if TeensyLatencySync is None:
            raise ImportError(
                "TeensyLatencySync dependency is unavailable. Ensure mouse_task is on PYTHONPATH "
                "and Teensy latency modules are installed."
            ) from import_issues
        return TeensyLatencySync(com, baudrate=baudrate)

    def save_latency_data(self) -> Dict[str, Any]:
        save_dict = super().save_latency_data()

        if self.use_teensy == 1:
            save_dict["ttl_read"] = np.array(getattr(self.teensy, "input_data_ttl", []))
            save_dict["teensy_time"] = np.array(
                getattr(self.teensy, "input_data_teensy_time", [])
            )

        return save_dict
    
    def set_dlc_cfg(self, dlc_cfg):
        self.dlc_cfg = dlc_cfg
    
    def on_recording_started(self, context: dict) -> None:
        """Receive recording context from DLCLiveGUI."""
        self.recording_context = dict(context or {})

        base_path = self.recording_context.get("processor_base_path")
        if base_path is None:
            self.save_path = None
            logger.warning("Processor recording started without processor_base_path")
            return

        base_path = Path(base_path)

        # Old-style processor output.
        self.save_path = base_path.parent / f"{base_path.name}_PROC"

        # Optional future outputs.
        self.dlc_h5_path = base_path.parent / f"{base_path.name}_DLC.hdf5"
        self.legacy_timestamp_path = base_path.parent / f"TS_{base_path.name}.npy"

        logger.info("Processor save path set to %s", self.save_path)
    
    def on_recording_stopped(self, context: dict) -> None:
        """Save custom processor outputs after GUI recording stops."""
        self.recording_context = dict(context or getattr(self, "recording_context", {}))

        # Save old PROC pickle.
        result = self.save()
        logger.info("Processor legacy PROC save result: %r", result)

        dlc_h5_result = self.save_legacy_dlc_h5()
        logger.info("Processor legacy DLC h5 save result: %r", dlc_h5_result)
        
        npy_ts_result = self.save_legacy_timestamp_npy()
        logger.info("Processor legacy timestamp npy save result: %r", npy_ts_result)
        
        try:
            self._legacy_poses.clear()
            self._legacy_pose_times.clear()
            self._legacy_frame_times.clear()
        except Exception:
            logger.warning("Failed to clear legacy pose buffers after recording stop")
    
    def save(self, file: Optional[str] = None) -> int:
        """Save processor data.

        If `file` is not provided, uses `self.save_path`.
        """
        target = file

        if target is None:
            target = getattr(self, "save_path", None)

        if target is None:
            warnings.warn("Processor save skipped: no file or save_path was provided.")
            return 0

        try:
            target = Path(target)
            target.parent.mkdir(parents=True, exist_ok=True)

            save_dict = self.save_latency_data()

            with target.open("wb") as f:
                pickle.dump(save_dict, f)

            print(f"Processor data saved to: {target}")
            return 1

        except Exception as e:
            warnings.warn(f"Proc file was not saved, an exception occurred: {e}")
            return -1
    
    def save_legacy_dlc_h5(self) -> int:
        """Write old-style <base>_DLC.hdf5 from buffered poses."""
        target = getattr(self, "dlc_h5_path", None)
        if target is None:
            logger.warning("Skipping DLC h5 save: no dlc_h5_path")
            return 0

        poses = np.asarray(getattr(self, "_legacy_poses", []))
        if poses.size == 0:
            logger.warning("Skipping DLC h5 save: no buffered poses")
            return 0

        try:
            target = Path(target)
            target.parent.mkdir(parents=True, exist_ok=True)

            # Expected shape: frames x keypoints x 3
            poses = np.asarray(poses)
            if poses.ndim == 2:
                # Single frame case.
                poses = poses[None, :, :]

            flat = poses.reshape((poses.shape[0], poses.shape[1] * poses.shape[2]))

            bodyparts = None
            dlc_cfg = getattr(self, "dlc_cfg", None)

            if isinstance(dlc_cfg, dict):
                bodyparts = (
                    dlc_cfg.get("all_joints_names")
                    or dlc_cfg.get("metadata", {}).get("bodyparts")
                )

            if bodyparts and len(bodyparts) * 3 == flat.shape[1]:
                pdindex = pd.MultiIndex.from_product(
                    [bodyparts, ["x", "y", "likelihood"]],
                    names=["bodyparts", "coords"],
                )
                pose_df = pd.DataFrame(flat, columns=pdindex)
            else:
                pose_df = pd.DataFrame(flat)

            pose_df["frame_time"] = list(getattr(self, "_legacy_frame_times", []))
            pose_df["pose_time"] = list(getattr(self, "_legacy_pose_times", []))

            pose_df.to_hdf(target, key="df_with_missing", mode="w")

            logger.info("Legacy DLC h5 saved to: %s", target)
            return 1

        except Exception:
            logger.exception("Failed to save legacy DLC h5")
            return -1
    
    def _extract_timestamps_from_json(self, json_path: Path) -> np.ndarray:
        """Extract software timestamps from new GUI timestamp JSON."""
        json_path = Path(json_path)

        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        # Current VideoRecorder schema.
        if isinstance(data, dict) and isinstance(data.get("frame_timestamps"), list):
            timestamps = []
            for rec in data["frame_timestamps"]:
                if isinstance(rec, dict) and "software_timestamp" in rec:
                    timestamps.append(float(rec["software_timestamp"]))
            return np.asarray(timestamps, dtype=float)

        # Tolerant fallback schemas.
        if isinstance(data, dict):
            for key in ("timestamps", "frame_times", "times"):
                values = data.get(key)
                if isinstance(values, list):
                    return np.asarray(values, dtype=float)

        if isinstance(data, list):
            values = []
            for item in data:
                if isinstance(item, (int, float)):
                    values.append(float(item))
                elif isinstance(item, dict):
                    for key in ("software_timestamp", "timestamp", "frame_time", "time"):
                        if key in item:
                            values.append(float(item[key]))
                            break
            return np.asarray(values, dtype=float)

        return np.asarray([], dtype=float)
    
    def _legacy_timestamp_output_path(
        self,
        json_path: Path,
        *,
        base_path: Path | None,
        index: int,
        total: int,
    ) -> Path:
        """Derive old-style TS_*.npy path from timestamp JSON path/context."""
        json_path = Path(json_path)

        # Single DLC/camera recording: use processor base name.
        if total == 1 and base_path is not None:
            return base_path.parent / f"TS_{base_path.name}.npy"

        # Multi-camera case: derive from video filename.
        name = json_path.name

        for suffix in (
            ".avi_timestamps.json",
            ".mp4_timestamps.json",
            "_timestamps.json",
        ):
            if name.endswith(suffix):
                video_stem = name[: -len(suffix)]
                break
        else:
            video_stem = json_path.stem

        return json_path.parent / f"TS_{video_stem}.npy"
    
    def _find_timestamp_json_files(self) -> list[Path]:
        """Resolve timestamp JSON files from recording context."""
        context = getattr(self, "recording_context", {}) or {}

        value = (
            context.get("timestamp_json_files")
            or context.get("timestamp_files")
            or {}
        )

        paths: list[Path] = []

        if isinstance(value, (str, Path)):
            paths.append(Path(value))

        elif isinstance(value, dict):
            for item in value.values():
                if isinstance(item, (str, Path)):
                    paths.append(Path(item))

        elif isinstance(value, (list, tuple, set)):
            for item in value:
                if isinstance(item, (str, Path)):
                    paths.append(Path(item))

        paths = [p for p in paths if p.exists()]

        if paths:
            return sorted(paths)

        # Fallback: scan run_dir.
        run_dir = context.get("run_dir")
        if run_dir is not None:
            return sorted(Path(run_dir).glob("*_timestamps.json"))

        return []
        
    def save_legacy_timestamp_npy(self) -> int:
        """Convert new GUI timestamp JSON files to old-style TS_*.npy files."""
        json_paths = self._find_timestamp_json_files()

        if not json_paths:
            logger.warning("Skipping legacy timestamp npy save: no timestamp JSON files found")
            return 0

        context = getattr(self, "recording_context", {}) or {}
        base_path = context.get("processor_base_path")
        base_path = Path(base_path) if base_path is not None else None

        saved = 0

        for index, json_path in enumerate(json_paths):
            try:
                timestamps = self._extract_timestamps_from_json(json_path)

                if timestamps.size == 0:
                    logger.warning("No timestamps extracted from %s", json_path)
                    continue

                out_path = self._legacy_timestamp_output_path(
                    json_path,
                    base_path=base_path,
                    index=index,
                    total=len(json_paths),
                )

                out_path.parent.mkdir(parents=True, exist_ok=True)
                np.save(out_path, timestamps)

                logger.info(
                    "Legacy timestamp npy saved to %s with %d timestamps",
                    out_path,
                    len(timestamps),
                )
                saved += 1

            except Exception:
                logger.exception("Failed to convert timestamp JSON to npy: %s", json_path)

        return 1 if saved else 0
    
    
    def stop(self, save: bool = False, file: str | None = None) -> None:
        """Cleanly stop processor resources.

        Args:
            save:
                If True, call self.save(file) before closing resources.
            file:
                Output path for processor data. If None, no save is attempted unless
                the parent class has a meaningful default filename.
        """

        # 1. Optional save first, while all buffers/objects still exist.
        if save:
            try:
                self.save(file)
            except Exception as exc:
                print(f"Processor save during stop failed: {exc}")

        # 2. Close Teensy serial if available.
        try:
            teensy = getattr(self, "teensy", None)
            if teensy is not None:
                close_serial = getattr(teensy, "close_serial", None)
                if callable(close_serial):
                    close_serial()
                else:
                    close = getattr(teensy, "close", None)
                    if callable(close):
                        close()
        except Exception as exc:
            print(f"Failed to close Teensy cleanly: {exc}")
        finally:
            try:
                self.teensy = None
            except Exception:
                pass

        # 3. Close accepted socket connection.
        try:
            conn = getattr(self, "conn", None)
            if conn is not None:
                conn.close()
        except Exception as exc:
            print(f"Failed to close processor socket connection: {exc}")
        finally:
            try:
                self.conn = None
            except Exception:
                pass

        # 4. Close listener on port 6000.
        try:
            listener = getattr(self, "listener", None)
            if listener is not None:
                listener.close()
        except Exception as exc:
            print(f"Failed to close processor listener: {exc}")
        finally:
            try:
                self.listener = None
            except Exception:
                pass


    def close(self) -> None:
        """Alias for generic cleanup."""
        self.stop(save=False)


def get_available_processors() -> Dict[str, Dict[str, Any]]:
    return {
        "dlc_inference_w_pd_sync": {
            "class": dlc_inference_w_pd_sync,
            "name": getattr(dlc_inference_w_pd_sync, "PROCESSOR_NAME", "dlc_inference_w_pd_sync"),
            "description": getattr(dlc_inference_w_pd_sync, "PROCESSOR_DESCRIPTION", ""),
            "params": getattr(dlc_inference_w_pd_sync, "PROCESSOR_PARAMS", {}),
        }
    }

"""Sync photodiode processor that reuses the shared DLC/socket behavior."""

from __future__ import annotations

from datetime import datetime
import importlib.util
import json
import logging
import pickle
import re
import shutil
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
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
    PROCESSOR_DESCRIPTION = "Photodiode processor with Teensy sync timing capture."

    # Legacy initialization ensures compatibility with old DLCLiveGUI processors:
    # sockets / serial / side-effect-heavy resources are created inside DLCLiveWorker.
    PROCESSOR_BUILD_IN_WORKER = True

    HEAD_CONF_THRESHOLD = 0.6 # NOTE: this might need to be adjusted based on the model

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
        com: str = "COM3",
        baudrate: int = 9600,
        signal_delay: float = 10,
        signal_type: str = "pulse_geo",
        freq: float = 5,
        use_teensy: int | bool = 1,
    ) -> None:
        self.recording_context: dict[str, Any] = {}

        self.save_path: Optional[Path] = None
        self.dlc_h5_path: Optional[Path] = None
        self.legacy_timestamp_path: Optional[Path] = None

        self._legacy_recording_active = False
        self._legacy_poses: list[np.ndarray] = []
        self._legacy_pose_times: list[float] = []
        self._legacy_frame_times: list[float] = []

        self.dlc_cfg = None

        try:
            super().__init__(
                com=com,
                baudrate=baudrate,
                signal_delay=signal_delay,
                signal_type=signal_type,
                freq=freq,
                use_teensy=use_teensy,
            )

            try:
                logger.info(
                    "Listener status: %s with authkey: %r",
                    self.listener._listener._socket.getsockname(),
                    self.authkey,
                )
            except Exception:
                logger.info("Listener initialized with authkey: %r", getattr(self, "authkey", None))

        except Exception as e:
            self.stop(save=False)
            raise RuntimeError(f"Failed to initialize dlc_inference_w_pd_sync: {e}.") from e

    # ------------------------------------------------------------------
    # DLCLive processor API
    # ------------------------------------------------------------------

    def process(self, pose: NDArray[np.float64], **kwargs: Any) -> NDArray[np.float64]:
        """Run the parent processor and buffer pose data for legacy DLC HDF5 saving."""
        processed_pose = super().process(pose, **kwargs)

        # Parent should return pose, but guard just in case.
        pose_to_buffer = processed_pose if processed_pose is not None else pose

        if self._legacy_recording_active:
            try:
                # Use float32 to reduce RAM pressure during long recordings.
                self._legacy_poses.append(np.asarray(pose_to_buffer, dtype=np.float32).copy())
                self._legacy_pose_times.append(time.time())
                self._legacy_frame_times.append(float(kwargs.get("frame_time", time.time())))
            except Exception:
                logger.exception("Failed to buffer pose for legacy DLC save")

        return pose_to_buffer

    def _create_teensy(self, com, baudrate):
        if TeensyLatencySync is None:
            raise ImportError(
                "TeensyLatencySync dependency is unavailable. Ensure mouse_task is on PYTHONPATH "
                "and Teensy latency modules are installed."
            ) from import_issues

        return TeensyLatencySync(com, baudrate=baudrate)

    def set_dlc_cfg(self, dlc_cfg):
        self.dlc_cfg = dlc_cfg

    # ------------------------------------------------------------------
    # Recording lifecycle hooks from DLCLiveGUI
    # ------------------------------------------------------------------

    def on_recording_started(self, context: dict) -> None:
        """Receive recording context from DLCLiveGUI."""
        self.recording_context = dict(context or {})

        base_path = self._context_processor_base_path()
        if base_path is None:
            self.save_path = None
            self.dlc_h5_path = None
            self.legacy_timestamp_path = None
            logger.warning("Processor recording started without processor_base_path")
            return

        # Primary/native processor outputs.
        self.save_path = base_path.parent / f"{base_path.name}_PROC"
        self.dlc_h5_path = base_path.parent / f"{base_path.name}_DLC.hdf5"

        # Single/base timestamp target. Per-video timestamp targets are derived later.
        self.legacy_timestamp_path = base_path.parent / f"{base_path.name}_TS.npy"

        self._legacy_recording_active = True
        self._legacy_poses.clear()
        self._legacy_pose_times.clear()
        self._legacy_frame_times.clear()

        logger.info("Processor save path set to %s", self.save_path)
        logger.info("Processor DLC h5 path set to %s", self.dlc_h5_path)
        logger.info("Processor timestamp path set to %s", self.legacy_timestamp_path)

    def on_recording_stopped(self, context: dict) -> None:
        """Save all custom legacy outputs after GUI recording stops."""
        previous_context = dict(getattr(self, "recording_context", {}) or {})
        previous_context.update(context or {})
        self.recording_context = previous_context

        self._legacy_recording_active = False

        proc_result = self.save()
        logger.info("Processor legacy PROC save result: %r", proc_result)

        dlc_h5_result = self.save_legacy_dlc_h5()
        logger.info("Processor legacy DLC h5 save result: %r", dlc_h5_result)

        npy_ts_result = self.save_legacy_timestamp_npy()
        logger.info("Processor legacy timestamp npy save result: %r", npy_ts_result)

        video_copy_result = self.copy_legacy_video_files()
        logger.info("Processor legacy video copy result: %r", video_copy_result)

        align_result = self.copy_processor_outputs_to_primary_legacy_base()
        logger.info("Processor legacy output alignment result: %r", align_result)

        self._clear_legacy_pose_buffers()

    # ------------------------------------------------------------------
    # Primary PROC save
    # ------------------------------------------------------------------

    def save_latency_data(self) -> Dict[str, Any]:
        save_dict = super().save_latency_data()

        if getattr(self, "use_teensy", 0) == 1:
            save_dict["ttl_read"] = np.array(getattr(self.teensy, "input_data_ttl", []))
            save_dict["teensy_time"] = np.array(
                getattr(self.teensy, "input_data_teensy_time", [])
            )

        return save_dict

    def save(self, file: str | Path | None = None) -> int:
        """Save processor PROC-style data.

        If `file` is not provided, uses `self.save_path`.
        """
        target = Path(file) if file is not None else getattr(self, "save_path", None)

        if target is None:
            warnings.warn("Processor save skipped: no file or save_path was provided.")
            return 0

        try:
            target = Path(target)
            target.parent.mkdir(parents=True, exist_ok=True)

            with target.open("wb") as f:
                pickle.dump(self.save_latency_data(), f)

            logger.info("Processor data saved to: %s", target)
            return 1

        except Exception as e:
            warnings.warn(f"Proc file was not saved, an exception occurred: {e}")
            logger.exception("Processor PROC save failed")
            return -1

    # ------------------------------------------------------------------
    # Legacy DLC HDF5 saving
    # ------------------------------------------------------------------

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

            if poses.ndim == 2:
                poses = poses[None, :, :]

            if poses.ndim != 3 or poses.shape[-1] != 3:
                logger.warning("Skipping DLC h5 save: unexpected pose shape %s", poses.shape)
                return 0

            flat = poses.reshape((poses.shape[0], poses.shape[1] * poses.shape[2]))

            bodyparts = self._get_bodyparts_for_pose_width(flat.shape[1])
            if bodyparts:
                pdindex = pd.MultiIndex.from_product(
                    [bodyparts, ["x", "y", "likelihood"]],
                    names=["bodyparts", "coords"],
                )
                pose_df = pd.DataFrame(flat, columns=pdindex)
            else:
                logger.warning("Bodyparts information not found or mismatched; saving DLC h5 without labels.")
                pose_df = pd.DataFrame(flat)

            pose_df["frame_time"] = list(self._legacy_frame_times)
            pose_df["pose_time"] = list(self._legacy_pose_times)

            pose_df.to_hdf(target, key="df_with_missing", mode="w")

            logger.info("Legacy DLC h5 saved to: %s", target)
            return 1

        except Exception:
            logger.exception("Failed to save legacy DLC h5")
            return -1

    def _get_bodyparts_for_pose_width(self, flat_width: int) -> list[str] | None:
        dlc_cfg = getattr(self, "dlc_cfg", None)
        bodyparts = None

        if isinstance(dlc_cfg, dict):
            bodyparts = (
                dlc_cfg.get("all_joints_names")
                or dlc_cfg.get("metadata", {}).get("bodyparts")
            )

        if bodyparts and len(bodyparts) * 3 == flat_width:
            return list(bodyparts)

        return None

    # ------------------------------------------------------------------
    # Timestamp JSON -> legacy NPY
    # ------------------------------------------------------------------

    def save_legacy_timestamp_npy(self) -> int:
        json_paths = self._find_timestamp_json_files()

        if not json_paths:
            logger.warning("Skipping legacy timestamp npy save: no timestamp JSON files found")
            return 0

        saved = 0
        total = len(json_paths)
        compat_base = self._db_compat_base()

        for index, json_path in enumerate(json_paths):
            try:
                timestamps = self._extract_timestamps_from_json(json_path)
                if timestamps.size == 0:
                    logger.warning("No timestamps extracted from %s", json_path)
                    continue

                for out_path in self._timestamp_output_paths(
                    compat_base,
                    index=index,
                    total=total,
                ):
                    self._save_npy(out_path, timestamps)
                    logger.info(
                        "DB-compatible timestamp npy saved to %s with %d timestamps",
                        out_path,
                        len(timestamps),
                    )
                    saved += 1

            except Exception:
                logger.exception("Failed to convert timestamp JSON to npy: %s", json_path)

        return 1 if saved else 0
    
    def _extract_timestamps_from_json(self, json_path: Path) -> np.ndarray:
        """Extract timestamps from the new VideoRecorder JSON format.

        Old GUI saved `np.save(..., write_frame_ts)`, i.e. a 1D numeric array.
        This returns the same shape/type.
        """
        json_path = Path(json_path)

        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict) and isinstance(data.get("frame_timestamps"), list):
            timestamps = [
                float(rec["software_timestamp"])
                for rec in data["frame_timestamps"]
                if isinstance(rec, dict) and "software_timestamp" in rec
            ]
            return np.asarray(timestamps, dtype=float)

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
                    value = self._first_present(item, ("software_timestamp", "timestamp", "frame_time", "time"))
                    if value is not None:
                        values.append(float(value))
            return np.asarray(values, dtype=float)

        return np.asarray([], dtype=float)

    def _find_timestamp_json_files(self) -> list[Path]:
        """Resolve timestamp JSON files from recording context."""
        paths = self._paths_from_context_value(
            self.recording_context.get("timestamp_json_files")
            or self.recording_context.get("timestamp_files")
        )

        paths = [p for p in paths if p.exists()]
        if paths:
            return sorted(paths)

        run_dir = self.recording_context.get("run_dir")
        if run_dir is not None:
            return sorted(Path(run_dir).glob("*_timestamps.json"))

        return []

    def _timestamp_output_paths(
        self,
        compat_base: Path,
        *,
        index: int,
        total: int,
    ) -> list[Path]:
        camera_token = "CAMERA" if total == 1 else f"CAMERA{index + 1}"

        return self._unique_paths(
            [
                compat_base.parent / f"TS_{compat_base.name}_{camera_token}.npy",
                # compat_base.parent / f"TIMESTAMP_{compat_base.name}_{camera_token}.npy",
            ]
        )

    # ------------------------------------------------------------------
    # Legacy video/sidecar compatibility copies
    # ------------------------------------------------------------------
    def copy_legacy_video_files(self) -> int:
        copied = 0
        video_files = self._find_video_files()
        compat_base = self._db_compat_base()
        total = len(video_files)

        for index, video_path in enumerate(video_files):
            try:
                video_token = "VIDEO" if total == 1 else f"VIDEO{index + 1}"
                out_path = compat_base.parent / f"{compat_base.name}_{video_token}{video_path.suffix}"

                if self._copy_file_if_needed(video_path, out_path):
                    copied += 1

            except Exception:
                logger.exception("Failed to copy DB-compatible video file %s", video_path)

        return 1 if copied else 0

    def copy_processor_outputs_to_primary_legacy_base(self) -> int:
        compat_base = self._db_compat_base()
        copied = 0

        src_proc = getattr(self, "save_path", None)
        if src_proc is not None:
            dst_proc = compat_base.parent / f"{compat_base.name}_PROC"
            if self._copy_file_if_needed(Path(src_proc), dst_proc):
                copied += 1

        src_h5 = getattr(self, "dlc_h5_path", None)
        if src_h5 is not None:
            dst_h5 = compat_base.parent / f"{compat_base.name}_DLC.hdf5"
            if self._copy_file_if_needed(Path(src_h5), dst_h5):
                copied += 1

        return 1 if copied else 0

    # ------------------------------------------------------------------
    # Legacy base / path helpers
    # ------------------------------------------------------------------
    def _video_prefix(self) -> str:
        videos = self._find_video_files()

        if videos:
            return videos[0].stem.split("_", 1)[0]

        filename_stem = self.recording_context.get("filename_stem")
        if filename_stem:
            return str(filename_stem).split("_", 1)[0]

        return "recording"
    
    def _db_compat_base(self) -> Path:
        """Return DB-GUI-compatible base path.

        New Live-GUI layout is usually:

            MouseA/run_<timestamp>/

        This returns:

            <run_dir>/MouseA_YYYY-MM-DD_1

        so files parse correctly as:
            mouse_name = MouseA
            date = YYYY-MM-DD
            attempt = 1
        """
        context = getattr(self, "recording_context", {}) or {}

        run_dir = context.get("run_dir")
        run_dir = Path(run_dir) if run_dir is not None else self._fallback_output_dir()

        prefix = self._video_prefix()
        # mouse = self._mouse_from_context_or_run_dir(run_dir)
        date = self._date_from_context_or_run_dir(run_dir)
        attempt = self._attempt_from_context(default="1")

        return run_dir / f"vr4mice_{prefix}_{date}_{attempt}"


    def _fallback_output_dir(self) -> Path:
        base_path = self._context_processor_base_path()
        if base_path is not None:
            return base_path.parent

        save_path = getattr(self, "save_path", None)
        if save_path is not None:
            return Path(save_path).parent

        return Path.cwd()


    def _mouse_from_context_or_run_dir(self, run_dir: Path) -> str:
        context = getattr(self, "recording_context", {}) or {}

        for key in ("mouse", "mouse_name", "subject", "session_name"):
            value = context.get(key)
            if value:
                return self._sanitize(str(value))

        # New Live-GUI layout: MouseA/run_<timestamp>/
        parent_name = getattr(run_dir.parent, "name", "")
        if parent_name:
            return self._sanitize(parent_name)

        return "Mouse"


    def _date_from_context_or_run_dir(self, run_dir: Path) -> str:
        context = getattr(self, "recording_context", {}) or {}

        for key in ("date", "recording_date", "session_date"):
            value = context.get(key)
            if value:
                parsed = self._normalize_date(str(value))
                if parsed:
                    return parsed

        parsed = self._date_from_run_dir_name(run_dir.name)
        if parsed:
            return parsed

        try:
            return datetime.fromtimestamp(run_dir.stat().st_mtime).strftime("%Y-%m-%d")
        except Exception:
            return datetime.now().strftime("%Y-%m-%d")


    def _attempt_from_context(self, default: str = "1") -> str:
        context = getattr(self, "recording_context", {}) or {}

        for key in ("attempt", "trial", "run_index"):
            value = context.get(key)
            if value not in (None, ""):
                return self._sanitize(str(value))

        filename_stem = context.get("filename_stem")
        if filename_stem:
            parts = str(filename_stem).split("_")
            for part in reversed(parts):
                if part.isdigit():
                    return self._sanitize(part)

        return default


    @staticmethod
    def _sanitize(value: str) -> str:
        value = str(value).strip()
        value = value.replace(" ", "")
        value = value.replace("_", "")
        return value or "unknown"


    @staticmethod
    def _normalize_date(value: str) -> str | None:
        value = str(value)

        # Already YYYY-MM-DD
        match = re.search(r"(20\d{2}-\d{2}-\d{2})", value)
        if match:
            return match.group(1)

        # YYYYMMDD
        match = re.search(r"(20\d{2})(\d{2})(\d{2})", value)
        if match:
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

        return None


    def _date_from_run_dir_name(self, run_name: str) -> str | None:
        return self._normalize_date(run_name)

    def _context_processor_base_path(self) -> Path | None:
        base_path = self.recording_context.get("processor_base_path")
        return Path(base_path) if base_path is not None else None

    def _primary_legacy_base(self) -> Path | None:
        return self._db_compat_base()

    def _legacy_base_for_timestamp_json(self, json_path: Path) -> Path:
        """Return legacy base path inferred from a timestamp JSON file."""
        json_path = Path(json_path)
        run_dir = Path(self.recording_context.get("run_dir") or json_path.parent)

        video_name = self._video_name_from_timestamp_json(json_path)
        if video_name:
            return run_dir / Path(video_name).stem

        return run_dir / self._strip_timestamp_json_suffix(json_path.name)

    def _legacy_base_for_video(self, video_path: Path) -> Path:
        """Return legacy base path inferred from a video path."""
        video_path = Path(video_path)
        return video_path.parent / video_path.stem

    def _video_name_from_timestamp_json(self, json_path: Path) -> str | None:
        try:
            with Path(json_path).open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                video_name = data.get("video_file")
                return str(video_name) if video_name else None
        except Exception:
            return None

        return None

    @staticmethod
    def _strip_timestamp_json_suffix(name: str) -> str:
        for suffix in (
            ".avi_timestamps.json",
            ".mp4_timestamps.json",
            "_timestamps.json",
        ):
            if name.endswith(suffix):
                return name[: -len(suffix)]
        return Path(name).stem

    def _find_video_files(self) -> list[Path]:
        paths = self._paths_from_context_value(self.recording_context.get("video_files"))
        paths = [p for p in paths if p.exists()]
        if paths:
            return sorted(paths)

        run_dir = self.recording_context.get("run_dir")
        if run_dir is None:
            return []

        run_dir = Path(run_dir)
        return sorted([*run_dir.glob("*.avi"), *run_dir.glob("*.mp4")])

    @staticmethod
    def _paths_from_context_value(value: Any) -> list[Path]:
        if value is None:
            return []

        if isinstance(value, (str, Path)):
            return [Path(value)]

        if isinstance(value, dict):
            return [Path(v) for v in value.values() if isinstance(v, (str, Path))]

        if isinstance(value, (list, tuple, set)):
            return [Path(v) for v in value if isinstance(v, (str, Path))]

        return []

    @staticmethod
    def _unique_paths(paths: list[Path]) -> list[Path]:
        unique: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            key = str(path)
            if key not in seen:
                unique.append(path)
                seen.add(key)
        return unique

    @staticmethod
    def _copy_file_if_needed(src: Path, dst: Path) -> bool:
        src = Path(src)
        dst = Path(dst)

        if not src.exists():
            return False

        try:
            if src.resolve() == dst.resolve():
                return False
        except Exception:
            if str(src) == str(dst):
                return False

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        logger.info("Copied compatibility file %s -> %s", src, dst)
        return True

    @staticmethod
    def _save_npy(path: Path, values: np.ndarray) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, values)

    @staticmethod
    def _first_present(mapping: dict, keys: tuple[str, ...]) -> Any:
        for key in keys:
            if key in mapping:
                return mapping[key]
        return None

    def _clear_legacy_pose_buffers(self) -> None:
        try:
            self._legacy_poses.clear()
            self._legacy_pose_times.clear()
            self._legacy_frame_times.clear()
        except Exception:
            logger.warning("Failed to clear legacy pose buffers after recording stop")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def stop(self, save: bool = False, file: str | Path | None = None) -> None:
        """Cleanly stop processor resources."""
        if save:
            try:
                self.save(file)
            except Exception:
                logger.exception("Processor save during stop failed")

        self._close_teensy()
        self._close_socket_connection()
        self._close_listener()

    def close(self) -> None:
        """Alias for generic cleanup."""
        self.stop(save=False)

    def _close_teensy(self) -> None:
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
        except Exception:
            logger.exception("Failed to close Teensy cleanly")
        finally:
            try:
                self.teensy = None
            except Exception:
                pass

    def _close_socket_connection(self) -> None:
        try:
            conn = getattr(self, "conn", None)
            if conn is not None:
                conn.close()
        except Exception:
            logger.exception("Failed to close processor socket connection")
        finally:
            try:
                self.conn = None
            except Exception:
                pass

    def _close_listener(self) -> None:
        try:
            listener = getattr(self, "listener", None)
            if listener is not None:
                listener.close()
        except Exception:
            logger.exception("Failed to close processor listener")
        finally:
            try:
                self.listener = None
            except Exception:
                pass


def get_available_processors() -> Dict[str, Dict[str, Any]]:
    return {
        "dlc_inference_w_pd_sync": {
            "class": dlc_inference_w_pd_sync,
            "name": getattr(dlc_inference_w_pd_sync, "PROCESSOR_NAME", "dlc_inference_w_pd_sync"),
            "description": getattr(dlc_inference_w_pd_sync, "PROCESSOR_DESCRIPTION", ""),
            "params": getattr(dlc_inference_w_pd_sync, "PROCESSOR_PARAMS", {}),
        }
    }
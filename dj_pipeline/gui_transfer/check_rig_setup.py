#!/usr/bin/env python3
"""
Preflight checks for gui_transfer on a rig (Windows or Linux).

Usage:
    python check_rig_setup.py
    python check_rig_setup.py --test-menu
"""

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

GUI_ROOT = Path(__file__).resolve().parent

RIG_PATH_KEYS = (
    "teensy_path",
    "dlc_path",
    "proc_path",
    "video_path",
    "camera_path",
    "raw_data_src",
)

AUTO_CREATE_PATH_KEYS = ("gui_output_folder", "processed_path")


def _ok(message):
    print(f"  OK   {message}")


def _fail(message):
    print(f"  FAIL {message}")


def _warn(message):
    print(f"  WARN {message}")


def check_python_version():
    if sys.version_info < (3, 9):
        return False, f"Python 3.9+ required (found {sys.version.split()[0]})"
    return True, f"Python {sys.version.split()[0]}"


def check_python_packages():
    missing = []
    for name in ("PyQt5", "numpy", "moviepy"):
        if importlib.util.find_spec(name) is None:
            missing.append(name)
    if missing:
        return False, "Missing packages: " + ", ".join(missing)
    return True, "PyQt5, numpy, moviepy installed"


def check_scp():
    if shutil.which("scp") is None:
        return False, "scp not found (install OpenSSH Client on Windows)"
    return True, "scp available"


def load_config():
    os.environ.setdefault("config_path", "default")
    os.environ.setdefault("config_name", "config.json")
    if str(GUI_ROOT) not in sys.path:
        sys.path.insert(0, str(GUI_ROOT))
    from config.config import get_system_config, validate_config

    config_dict = get_system_config()
    if config_dict is False:
        return False, "config/config.json not found", None
    ok, message = validate_config(config_dict)
    if not ok:
        return False, message, config_dict
    return True, "config/config.json valid", config_dict


def check_rig_paths(config_dict):
    warnings = []
    for key in RIG_PATH_KEYS:
        value = config_dict.get(key)
        if not value or value == "default":
            continue
        path = Path(value)
        if not path.is_dir():
            warnings.append(f"{key} folder missing: {path}")
    for key in AUTO_CREATE_PATH_KEYS:
        value = config_dict.get(key)
        if not value or value == "default":
            continue
        path = Path(value)
        if not path.is_dir():
            warnings.append(f"{key} will be created on first use: {path}")
    return warnings


def test_menu_access(config_dict):
    ip = str(config_dict.get("ip", ""))
    if "localhost" in ip:
        src = Path(config_dict["remote_dropdown_menu"])
        if not src.is_file():
            return False, f"Menu file not found locally: {src}"
        return True, f"Menu source readable: {src}"

    host = str(config_dict.get("host", "")).strip()
    remote = config_dict["remote_dropdown_menu"]
    dst = Path(config_dict["host_dropdown_menu"])
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst_str = str(dst).replace("\\", "/")
    cmd = [
        "scp",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=15",
        f"{host}@{ip}:{remote}",
        dst_str,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        return False, f"Menu scp failed: {' '.join(cmd)} — {detail}"
    if not dst.is_file():
        return False, f"Menu scp succeeded but file missing: {dst}"
    return True, f"Menu downloaded to {dst}"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Preflight checks for gui_transfer rig setup."
    )
    parser.add_argument(
        "--test-menu",
        action="store_true",
        help="Test menu file access (local copy or scp from server). Uses BatchMode for scp.",
    )
    args = parser.parse_args(argv)

    print("gui_transfer rig preflight\n")

    failures = 0

    ok, message = check_python_version()
    (_ok if ok else _fail)(message)
    failures += 0 if ok else 1

    ok, message = check_python_packages()
    (_ok if ok else _fail)(message)
    failures += 0 if ok else 1

    ok, message = check_scp()
    (_ok if ok else _fail)(message)
    failures += 0 if ok else 1

    ok, message, config_dict = load_config()
    (_ok if ok else _fail)(message)
    failures += 0 if ok else 1

    if config_dict:
        for warning in check_rig_paths(config_dict):
            _warn(warning)

    if args.test_menu:
        if not config_dict:
            _fail("--test-menu skipped (config invalid)")
            failures += 1
        else:
            ok, message = test_menu_access(config_dict)
            (_ok if ok else _fail)(message)
            failures += 0 if ok else 1

    print()
    if failures:
        print(
            f"Preflight failed ({failures} check(s)). Fix the items above, then retry."
        )
        print(
            "Tip: run `python check_rig_setup.py --test-menu` after SSH keys are set up."
        )
        return 1

    print("Preflight passed.")
    if not args.test_menu:
        print("Optional: run with --test-menu to verify menu download from the server.")
    print("Start the GUI with run_gui.bat (Windows) or `python main.py`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

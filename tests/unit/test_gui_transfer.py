"""
Unit tests for dj_pipeline/gui_transfer (rig PyQt GUI helpers).

These tests cover config loading, menu fetch, metadata helpers, and localhost
file transfer without opening the GUI window.
"""

import importlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GUI_TRANSFER = PROJECT_ROOT / "dj_pipeline" / "gui_transfer"


@pytest.fixture
def sample_menu_dict():
    return {
        "MouseDict": {"Testmouse": {"mouse_name": "Testmouse"}},
        "experimenter_name": ["alice"],
    }


@pytest.fixture
def gui_config_paths(tmp_path, sample_menu_dict):
    menu_src = tmp_path / "remote_menu.npy"
    np.save(menu_src, sample_menu_dict, allow_pickle=True)
    menu_dst = tmp_path / "host_menu.npy"

    config_data = {
        "ip": "localhost",
        "host": "",
        "remote_dropdown_menu": str(menu_src),
        "host_dropdown_menu": str(menu_dst),
        "gui_output_folder": str(tmp_path / "output"),
        "cache": str(tmp_path / "cache.json"),
        "remote_dst": str(tmp_path / "remote"),
        "raw_data_src": str(tmp_path / "raw"),
        "dlc_path": str(tmp_path / "dlc"),
        "proc_path": str(tmp_path / "proc"),
        "video_path": str(tmp_path / "video"),
        "camera_path": str(tmp_path / "camera"),
        "teensy_path": str(tmp_path / "teensy"),
        "processed_path": str(tmp_path / "processed"),
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data))
    return config_file, menu_src, menu_dst, config_data


def _reload_gui_modules(config_file):
    os.environ["config_path"] = str(config_file)
    os.environ["config_name"] = "config.json"

    if str(GUI_TRANSFER) not in sys.path:
        sys.path.insert(0, str(GUI_TRANSFER))

    for name in list(sys.modules):
        if name in {
            "config.config",
            "utils.utils",
            "modules.transfer",
        } or name.startswith(("utils.", "modules.", "config.")):
            del sys.modules[name]

    config_mod = importlib.import_module("config.config")
    return importlib.reload(config_mod)


@pytest.fixture
def gui_modules(gui_config_paths):
    config_file, menu_src, menu_dst, config_data = gui_config_paths
    config_mod = _reload_gui_modules(config_file)
    utils_mod = importlib.import_module("utils.utils")
    return {
        "config": config_mod,
        "utils": utils_mod,
        "menu_src": menu_src,
        "menu_dst": menu_dst,
        "config_data": config_data,
        "config_file": config_file,
    }


@pytest.fixture
def transfer_module(gui_modules):
    return importlib.import_module("modules.transfer")


def test_get_system_config_defaults_without_env(monkeypatch):
    monkeypatch.delenv("config_path", raising=False)
    monkeypatch.delenv("config_name", raising=False)

    if str(GUI_TRANSFER) not in sys.path:
        sys.path.insert(0, str(GUI_TRANSFER))

    config_mod = importlib.import_module("config.config")
    config_mod = importlib.reload(config_mod)

    loaded = config_mod.get_system_config()
    assert isinstance(loaded, dict)
    assert "ip" in loaded


def test_get_menu_path_localhost_copy(gui_modules):
    path = gui_modules["config"].config.get_menu_path
    assert path == str(gui_modules["menu_dst"])
    assert gui_modules["menu_dst"].exists()
    loaded = np.load(gui_modules["menu_dst"], allow_pickle=True).item()
    assert loaded["experimenter_name"] == ["alice"]


def test_get_menu_path_missing_source_returns_false(gui_modules):
    config_data = gui_modules["config_data"]
    config_data["remote_dropdown_menu"] = "/nonexistent/gui_menu.npy"
    gui_modules["config_file"].write_text(json.dumps(config_data))
    config_mod = _reload_gui_modules(gui_modules["config_file"])
    assert config_mod.config.get_menu_path is False


def test_get_menu_path_same_path_skips_copy(gui_modules):
    config_data = gui_modules["config_data"]
    config_data["host_dropdown_menu"] = str(gui_modules["menu_src"])
    gui_modules["config_file"].write_text(json.dumps(config_data))
    config_mod = _reload_gui_modules(gui_modules["config_file"])
    assert config_mod.config.get_menu_path == str(gui_modules["menu_src"])


def test_load_dj_input(gui_modules):
    utils = gui_modules["utils"]
    cache = gui_modules["config_data"]["cache"]
    dj_dict, date, json_dict = utils.load_dj_input(
        path_dj_data=str(gui_modules["menu_src"]),
        path_json=cache,
    )
    assert dj_dict["experimenter_name"] == ["alice"]
    assert isinstance(date, str)
    assert json_dict == {}


def test_get_dataset(gui_modules):
    utils = gui_modules["utils"]
    dataset = utils.get_dataset(
        {"mouse_name": "Testmouse"},
        {"doe": "2023-02-22", "attempt": 2},
    )
    assert dataset == "Testmouse_2023-02-22_2"


def test_check_file_format_teensy(gui_modules):
    utils = gui_modules["utils"]
    result = utils.check_file_format(
        "teensy",
        "Testmouse_2023-02-22_2.pickle",
        "*_*_*.pickle",
    )
    assert result == ("Testmouse", "2", "2023-02-22")


def test_check_file_format_camera(gui_modules):
    utils = gui_modules["utils"]
    result = utils.check_file_format(
        "camera",
        "TS_Testmouse_2023-02-22_2.npy",
        "TS_*_*_*.npy",
    )
    assert result == ("Testmouse", "2", "2023-02-22")


def test_get_type(transfer_module):
    get_type = transfer_module.get_type
    assert get_type("Imagingsource_Testmouse_2023-02-22_2_VIDEO.mp4") == "video_path"
    assert get_type("TS_Testmouse_2023-02-22_2.npy") == "camera_path"
    assert get_type("Imagingsource_Testmouse_2023-02-22_2_DLC.hdf5") == "dlc_path"
    assert get_type("Imagingsource_Testmouse_2023-02-22_2_PROC") == "proc_path"
    assert get_type("Testmouse_2023-02-22_2.pickle") == "teensy_path"


def test_transfer_file_localhost_copy(gui_modules, tmp_path):
    utils = gui_modules["utils"]
    src_dir = tmp_path / "src"
    dst_dir = tmp_path / "dst"
    src_dir.mkdir()
    dst_dir.mkdir()
    sample = src_dir / "Testmouse_2023-02-22_2.pickle"
    sample.write_text("pickle-bytes")

    ok, path = utils._transfer_file(
        {"src": str(src_dir), "dst": str(dst_dir), "filename": sample.name},
        "localhost:",
    )
    assert ok is True
    assert (dst_dir / sample.name).exists()
    assert path == sample


def test_check_file_format_dlc(gui_modules):
    utils = gui_modules["utils"]
    result = utils.check_file_format(
        "dlc_path",
        "Imagingsource_Testmouse_2023-02-22_2_DLC.hdf5",
        ["*DLC*.h5", "*DLC*_meta.pickle", "*_*_*_*_DLC.hdf5"],
    )
    assert result == ("Testmouse", "2", "2023-02-22")


def test_move_files(gui_modules, tmp_path):
    utils = gui_modules["utils"]
    processed = Path(gui_modules["config_data"]["processed_path"])
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    sample = src_dir / "Testmouse_2023-02-22_2.pickle"
    sample.write_text("pickle-bytes")

    utils.move_files(
        [
            {
                "src": str(src_dir),
                "dst": str(tmp_path / "remote"),
                "filename": sample.name,
            }
        ]
    )
    assert (processed / sample.name).exists()
    assert not sample.exists()


def test_config_validate(gui_modules):
    ok, message = gui_modules["config"].Config.validate()
    assert ok is True
    assert message == ""


def test_find_related_files(gui_modules, tmp_path):
    from utils.session_files import find_related_files
    from modules.transfer import get_type

    config_data = gui_modules["config_data"]
    dlc_dir = Path(config_data["dlc_path"])
    teensy_dir = Path(config_data["teensy_path"])
    dlc_dir.mkdir(parents=True, exist_ok=True)
    teensy_dir.mkdir(parents=True, exist_ok=True)

    stem = "Testmouse_2023-02-22_2"
    teensy = teensy_dir / f"{stem}.pickle"
    ts = dlc_dir / f"TS_{stem}.npy"
    dlc = dlc_dir / f"Imagingsource_{stem}_DLC.hdf5"
    teensy.write_text("p")
    ts.write_text("t")
    dlc.write_text("d")

    path_by_key = {
        k: config_data[k]
        for k in config_data
        if k.endswith("_path") or k == "raw_data_src"
    }
    related = find_related_files(stem, path_by_key, get_type)
    assert related["teensy_path"] == teensy
    assert related["camera_path"] == ts
    assert related["dlc_path"] == dlc


def test_adjust_keys_uses_display_text(gui_modules):
    utils = gui_modules["utils"]
    info = {"Rig": "12 - AR"}
    key2info = {"12 - AR": 12}
    primary_keys = {"Rig": "rig_id"}
    utils.adjust_keys(info, {"Rig": None}, key2info, primary_keys)
    assert info == {"rig_id": 12}

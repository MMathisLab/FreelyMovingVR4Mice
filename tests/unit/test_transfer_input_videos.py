"""Unit tests for dj_pipeline/backup/transfer_input_videos.py."""

import importlib.util
from pathlib import Path

import pytest

_PATH = (
    Path(__file__).parent.parent.parent
    / "dj_pipeline"
    / "backup"
    / "transfer_input_videos.py"
)
_spec = importlib.util.spec_from_file_location("transfer_input_videos", _PATH)
transfer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(transfer)


def _touch(path, size=10):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


@pytest.fixture
def sources(tmp_path):
    obs = tmp_path / "Videos"
    _touch(obs / "Xestia_2026-06-29_1.mp4")
    _touch(obs / "Jacana_2024-07-26 _1.mkv")
    _touch(obs / "notes.txt")
    cam = tmp_path / "Videos_dlc"
    run = cam / "Xestia_2026-08-21_1" / "run_0001"
    _touch(run / "vr4mice_Xestia_2026-08-21_1_VIDEO2.avi", 30)
    _touch(run / "TS_vr4mice_Xestia_2026-08-21_1_CAMERA2.npy", 5)
    _touch(run / "vr4mice_Xestia_2026-08-21_1_VIDEO3.avi")
    # session whose camera files carry the wrong attempt number
    bad = cam / "Yurumi_2026-08-11_2" / "run_0001"
    _touch(bad / "vr4mice_Yurumi_2026-08-11_1_VIDEO2.avi")
    _touch(bad / "TS_vr4mice_Yurumi_2026-08-11_1_CAMERA2.npy")
    # old-setup session: no camera-2 files
    _touch(cam / "Whale_2026-07-22_1" / "run_0001" / "Whale_opencv_cam1.avi")
    return obs, cam, tmp_path / "share"


def test_obs_names_normalized(sources):
    obs, _, dest = sources
    copies = transfer.plan_obs(obs, dest, None, None)
    assert sorted(c.dst.name for c in copies) == [
        "Jacana_2024-07-26_1.mkv",
        "Xestia_2026-06-29_1.mp4",
    ]
    assert all(c.dst.parent == dest / "raw_screen_recordings" for c in copies)


def test_camera_pairs_flat_and_mismatch_reported(sources):
    _, cam, dest = sources
    problems = []
    copies = transfer.plan_camera(cam, dest, None, None, False, problems)
    assert sorted(c.dst.name for c in copies) == [
        "TS_vr4mice_Xestia_2026-08-21_1_CAMERA2.npy",
        "vr4mice_Xestia_2026-08-21_1_VIDEO2.avi",
    ]
    assert all(c.dst.parent == dest / "raw_input_videos" for c in copies)
    assert len(problems) == 1 and "Yurumi_2026-08-11_2" in problems[0]


def test_fix_names_uses_folder_dataset(sources):
    _, cam, dest = sources
    copies = transfer.plan_camera(
        cam, dest, ["Yurumi_2026-08-11_2"], None, True, problems := []
    )
    assert not problems
    assert sorted(c.dst.name for c in copies) == [
        "TS_vr4mice_Yurumi_2026-08-11_2_CAMERA2.npy",
        "vr4mice_Yurumi_2026-08-11_2_VIDEO2.avi",
    ]


def test_several_runs_with_camera_files_skipped(sources):
    _, cam, dest = sources
    run2 = cam / "Xestia_2026-08-21_1" / "run_0002"
    _touch(run2 / "vr4mice_Xestia_2026-08-21_1_VIDEO2.avi")
    _touch(run2 / "TS_vr4mice_Xestia_2026-08-21_1_CAMERA2.npy")
    problems = []
    copies = transfer.plan_camera(
        cam, dest, ["Xestia_2026-08-21_1"], None, False, problems
    )
    assert copies == [] and "several runs" in problems[0]


def test_dry_run_copies_nothing(sources):
    obs, cam, dest = sources
    assert (
        transfer.main(
            ["--dest", str(dest), "--obs-src", str(obs), "--camera-src", str(cam)]
        )
        == 0
    )
    assert not dest.exists()


def test_run_copies_then_skips_and_never_overwrites(sources):
    obs, cam, dest = sources
    args = [
        "--dest",
        str(dest),
        "--obs-src",
        str(obs),
        "--camera-src",
        str(cam),
        "--run",
    ]
    assert transfer.main(args) == 0
    video = dest / "raw_input_videos" / "vr4mice_Xestia_2026-08-21_1_VIDEO2.avi"
    assert video.stat().st_size == 30
    assert (dest / "raw_screen_recordings" / "Jacana_2024-07-26_1.mkv").exists()
    assert not list(dest.rglob("*.part"))

    # second run: same sizes -> already there, exit 0
    assert transfer.main(args) == 0
    # a different file already at the destination is not overwritten
    video.write_bytes(b"y" * 7)
    assert transfer.main(args) == 1
    assert video.stat().st_size == 7


def test_since_filter(sources):
    obs, _, dest = sources
    copies = transfer.plan_obs(obs, dest, None, transfer.date(2026, 1, 1))
    assert [c.dataset for c in copies] == ["Xestia_2026-06-29_1"]

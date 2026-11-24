"""Unit tests for the 3-camera input video helpers in analysis/inputs_videos.py."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import cv2
import numpy as np
import pandas as pd
import pytest

# conftest mocks the vr4mice.analysis package; inputs_videos imports
# vr4mice.analysis.latency_testing, so register the real module under that name.
import latency_testing

sys.modules.setdefault("vr4mice.analysis.latency_testing", latency_testing)

from inputs_videos import (  # noqa: E402
    align_steps_to_frames_by_photodiode,
    audit_video_files,
    check_camera_timestamps,
    match_edge_times,
    measure_seek_offset,
    verify_sync_against_photodiode,
    align_steps_to_frames_by_timestamps,
    binarize_sync_trace,
    crop_frame,
    find_scene_changes,
    iter_video_panels,
    resize_frame,
    find_input_video_files,
    find_sync_square,
    list_input_video_files,
    read_sync_trace,
    read_video_frame,
    step_alignment_qa,
)

FRAME_TIMES = np.array([10.0, 10.1, 10.2, 10.3, 10.4])


@pytest.fixture
def video_schema(monkeypatch):
    class TableMeta(type):
        def __and__(cls, key):
            return cls

    class Table(metaclass=TableMeta):
        pass

    monkeypatch.setitem(
        sys.modules,
        "datajoint",
        SimpleNamespace(Computed=Table, Imported=Table, Lookup=Table, Manual=Table),
    )
    monkeypatch.setitem(
        sys.modules,
        "vr4mice.utils.schema_config",
        SimpleNamespace(get_schema=lambda *_: lambda cls: cls),
    )
    monkeypatch.setitem(
        sys.modules, "vr4mice.analysis.inputs_videos", sys.modules["inputs_videos"]
    )
    schema_path = (
        Path(__file__).resolve().parents[2]
        / "dj_pipeline/vr4mice/schema/inputs_videos.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_input_video_test_schema", schema_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_query_frames_uses_camera_timestamps(video_schema, monkeypatch):
    alignment = video_schema.StepVideoFrame
    monkeypatch.setattr(
        alignment,
        "fetch1",
        MagicMock(
            return_value=([-0.05, 0.05, 0.15, 0.3], None, "camera", None, None, 0.05)
        ),
        raising=False,
    )
    state = MagicMock()
    state.__and__.return_value.fetch1.return_value = [10.0]
    monkeypatch.setattr(video_schema, "vr4mice", SimpleNamespace(State=state))
    monkeypatch.setattr(
        video_schema.InputVideo,
        "fetch1",
        MagicMock(return_value=FRAME_TIMES[:3]),
        raising=False,
    )

    queries = [-0.01, 0.06, 0.1, 0.25]
    captured = alignment.align_step_to_frames({}, queries, displayed=False)
    assert captured == [None, 1, 1, None]
    assert alignment.align_step_to_frames({}, [0.06, 0.18]) == [2, None]


def test_query_frames_uses_obs_clock_fit(video_schema, monkeypatch):
    alignment = video_schema.StepVideoFrame
    monkeypatch.setattr(
        alignment,
        "fetch1",
        MagicMock(return_value=([0.0, 0.05, 0.15, 0.3], None, "obs", -0.02, 1.5, 0.07)),
        raising=False,
    )
    monkeypatch.setattr(
        video_schema.RawVideoSync,
        "fetch1",
        MagicMock(return_value=(10.0, 4)),
        raising=False,
    )

    queries = [0.0, 0.06, 0.13, 0.21]
    captured = alignment.align_step_to_frames({}, queries, displayed=False)
    assert captured == [None, 1, 2, 3]
    assert alignment.align_step_to_frames({}, queries) == [1, 2, 3, None]
    with pytest.raises(ValueError, match="out of bounds"):
        alignment.align_step_to_frames({}, [0.31])


def test_query_frames_use_the_stored_corrected_obs_clock(video_schema, monkeypatch):
    # The stored mapping includes a +0.1 s residual correction after the first
    # step (dropped frames) that offset + drift alone (here the identity) misses.
    # The first step is outside the video.
    step_time = [0.0, 0.1, 0.2, 0.3]
    step_video_time = [np.nan, 0.2, 0.3, 0.4]
    alignment = video_schema.StepVideoFrame
    monkeypatch.setattr(
        alignment,
        "fetch1",
        MagicMock(return_value=(step_time, step_video_time, "obs", 0.0, 1.0, 0.1)),
        raising=False,
    )
    monkeypatch.setattr(
        video_schema.RawVideoSync,
        "fetch1",
        MagicMock(return_value=(10.0, 6)),
        raising=False,
    )

    # A step's own time returns the frame make() stored for it
    assert alignment.align_step_to_frames({}, step_time[1:], displayed=False) == [
        2,
        3,
        4,
    ]
    assert alignment.align_step_to_frames({}, [0.15, 0.3]) == [4, 5]
    assert alignment.align_step_to_frames({}, [0.0], displayed=False) == [None]


class _Rows:
    """Table stand-in: rows (dicts) restricted by dict keys they share."""

    def __init__(self, *rows):
        self.rows = list(rows)

    def __and__(self, key):
        keys = key if isinstance(key, list) else [key]  # a list restricts by OR
        return _Rows(
            *(
                r
                for r in self.rows
                if any(all(r[k] == v for k, v in k_.items() if k in r) for k_ in keys)
            )
        )

    def __bool__(self):
        return bool(self.rows)

    def fetch1(self, *attributes):
        (row,) = self.rows
        if not attributes:
            return dict(row)
        values = tuple(row[a] for a in attributes)
        return values[0] if len(values) == 1 else values


def test_obs_session_waits_for_its_batch_layout_without_failing(
    video_schema, monkeypatch
):
    failures = []

    class State:
        def __and__(self, _key):
            return self

        def fetch1(self, *attributes):
            raise RuntimeError("alignment attempted")

    class FailedSession:
        should_skip = staticmethod(lambda *args: False)

        def add_entry(self, *args):
            failures.append(args)

    def use(batches, layouts):
        monkeypatch.setattr(
            video_schema,
            "vr4mice",
            SimpleNamespace(
                FailedSession=FailedSession,
                DatasetBatch=_Rows(*batches),
                State=State(),
            ),
        )
        monkeypatch.setattr(video_schema, "ObsVideoLayout", _Rows(*layouts))
        monkeypatch.setattr(video_schema, "InputVideo", _Rows())

    key = {"dataset": "d"}
    batch3 = {"dataset": "d", "batch_name": "batch3"}
    table = video_schema.StepVideoFrame()

    use([], [])  # not in DatasetBatch yet
    table.make(key)
    use([batch3], [{"batch_name": "batch2"}])  # batch3 has no layout yet
    table.make(key)
    assert failures == []

    # Once the layout is added, the session is aligned (here: fails further on)
    use([batch3], [{"batch_name": "batch3"}])
    table.make(key)
    assert [args[:2] for args in failures] == [("d", "StepVideoFrame")]
    assert "alignment attempted" in failures[0][2]


def test_iter_video_panels_reports_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError, match="missing.avi"):
        list(iter_video_panels(tmp_path / "missing.avi", [0], (0, 0, 8, 6), (4, 3)))


def test_iter_video_panels_reuses_decoder_and_corrects_seeks(monkeypatch, tmp_path):
    class Capture:
        frame = 0
        released = False

        def isOpened(self):
            return True

        def get(self, prop):
            assert prop == cv2.CAP_PROP_FRAME_COUNT
            return 200

        def set(self, prop, value):
            assert prop == cv2.CAP_PROP_POS_FRAMES
            self.frame = value - 6
            return True

        def grab(self):
            self.frame += 1
            return True

        def read(self):
            frame = np.full((8, 10, 3), self.frame, dtype=np.uint8)
            self.frame += 1
            return True, frame

        def release(self):
            self.released = True

    cap = Capture()
    monkeypatch.setattr(cv2, "VideoCapture", lambda _: cap)
    path = tmp_path / "video.avi"
    path.touch()
    panels = list(
        iter_video_panels(path, [2, 195, 199], (1, 2, 8, 6), (4, 3), seek_offset=-6)
    )
    assert [panel.shape for panel in panels] == [(3, 4, 3)] * 3
    assert [panel[0, 0, 0] for panel in panels] == [2, 195, 199]
    assert cap.released


class TestAlignStepsToFramesByTimestamps:
    def test_exact_hit_matches_that_frame(self):
        frames = align_steps_to_frames_by_timestamps([10.0, 10.2, 10.4], FRAME_TIMES)
        np.testing.assert_array_equal(frames, [0, 2, 4])

    def test_between_frames_takes_next_frame(self):
        frames = align_steps_to_frames_by_timestamps([10.05, 10.29], FRAME_TIMES)
        np.testing.assert_array_equal(frames, [1, 3])

    def test_outside_video_is_minus_one(self):
        frames = align_steps_to_frames_by_timestamps([9.0, 10.41, np.nan], FRAME_TIMES)
        np.testing.assert_array_equal(frames, [-1, -1, -1])

    def test_frame_offset_shifts_and_flags_out_of_range(self):
        frames = align_steps_to_frames_by_timestamps(
            [10.0, 10.2, 10.4], FRAME_TIMES, frame_offset=-1
        )
        np.testing.assert_array_equal(frames, [-1, 1, 3])
        frames = align_steps_to_frames_by_timestamps(
            [10.0, 10.4], FRAME_TIMES, frame_offset=1
        )
        np.testing.assert_array_equal(frames, [1, -1])

    def test_returns_integers(self):
        frames = align_steps_to_frames_by_timestamps([10.1], FRAME_TIMES)
        assert frames.dtype == np.int64

    def test_unsorted_frame_times_rejected(self):
        with pytest.raises(ValueError, match="sorted"):
            align_steps_to_frames_by_timestamps([10.0], [10.0, 10.2, 10.1])

    def test_empty_frame_times_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            align_steps_to_frames_by_timestamps([10.0], [])


class TestStepAlignmentQa:
    def test_counts_coverage_and_gap(self):
        steps = np.array([9.0, 10.05, 10.2, 10.35])
        frames = align_steps_to_frames_by_timestamps(steps, FRAME_TIMES)
        qa = step_alignment_qa(steps, FRAME_TIMES, frames)
        assert qa["n_steps"] == 4
        assert qa["n_steps_outside_video"] == 1
        assert qa["coverage"] == pytest.approx(0.75)
        # gaps: 0.05, 0.0, 0.05 -> median 0.05
        assert qa["median_abs_gap"] == pytest.approx(0.05)

    def test_no_step_inside_video(self):
        steps = np.array([1.0, 2.0])
        frames = align_steps_to_frames_by_timestamps(steps, FRAME_TIMES)
        qa = step_alignment_qa(steps, FRAME_TIMES, frames)
        assert qa["coverage"] == 0.0
        assert np.isnan(qa["median_abs_gap"])

    def test_wrong_session_video_has_low_coverage(self):
        """A video recorded 40 min later does not cover this session's steps."""
        steps = np.linspace(0, 600, 1000)
        later_video = np.linspace(2400, 3000, 5000)
        frames = align_steps_to_frames_by_timestamps(steps, later_video)
        assert step_alignment_qa(steps, later_video, frames)["coverage"] == 0.0


class TestFindInputVideoFiles:
    def test_pairs_video_and_timestamps(self):
        names = [
            "vr4mice_Xestia_2026-08-21_1_VIDEO2.avi",
            "TS_vr4mice_Xestia_2026-08-21_1_CAMERA2.npy",
        ]
        assert find_input_video_files(names, ["vr4mice"]) == {
            "Xestia_2026-08-21_1": (
                "vr4mice_Xestia_2026-08-21_1_VIDEO2.avi",
                "TS_vr4mice_Xestia_2026-08-21_1_CAMERA2.npy",
            )
        }

    def test_both_files_required(self):
        names = [
            "vr4mice_Xestia_2026-08-21_1_VIDEO2.avi",
            "TS_vr4mice_Yurumi_2026-08-21_1_CAMERA2.npy",
        ]
        assert find_input_video_files(names, ["vr4mice"]) == {}

    def test_other_cameras_ignored(self):
        names = [
            "vr4mice_Xestia_2026-08-21_1_VIDEO3.avi",
            "TS_vr4mice_Xestia_2026-08-21_1_CAMERA3.npy",
            "vr4mice_Xestia_2026-08-21_1_VIDEO1.avi",
            "TS_vr4mice_Xestia_2026-08-21_1_CAMERA1.npy",
        ]
        assert find_input_video_files(names, ["vr4mice"]) == {}

    def test_attempt_numbers_kept_apart(self):
        names = [
            "vr4mice_Yurumi_2026-08-11_1_VIDEO2.avi",
            "TS_vr4mice_Yurumi_2026-08-11_1_CAMERA2.npy",
            "vr4mice_Yurumi_2026-08-11_2_VIDEO2.avi",
            "TS_vr4mice_Yurumi_2026-08-11_2_CAMERA2.npy",
        ]
        found = find_input_video_files(names, ["vr4mice"])
        assert sorted(found) == ["Yurumi_2026-08-11_1", "Yurumi_2026-08-11_2"]
        assert found["Yurumi_2026-08-11_2"][0] == (
            "vr4mice_Yurumi_2026-08-11_2_VIDEO2.avi"
        )

    def test_unknown_prefix_ignored_and_first_prefix_wins(self):
        names = [
            "other_Xestia_2026-08-21_1_VIDEO2.avi",
            "TS_other_Xestia_2026-08-21_1_CAMERA2.npy",
            "vr4mice_Xestia_2026-08-21_1_VIDEO2.avi",
            "TS_vr4mice_Xestia_2026-08-21_1_CAMERA2.npy",
            "Imagingsource_Xestia_2026-08-21_1_VIDEO2.avi",
            "TS_Imagingsource_Xestia_2026-08-21_1_CAMERA2.npy",
        ]
        found = find_input_video_files(names, ["Imagingsource", "vr4mice"])
        assert found["Xestia_2026-08-21_1"][0].startswith("Imagingsource_")
        assert find_input_video_files(names[:2], ["vr4mice"]) == {}


class TestListInputVideoFiles:
    def test_lists_full_paths_of_complete_pairs(self, tmp_path):
        for name in (
            "vr4mice_Xestia_2026-08-21_1_VIDEO2.avi",
            "TS_vr4mice_Xestia_2026-08-21_1_CAMERA2.npy",
            "vr4mice_Yurumi_2026-08-21_1_VIDEO2.avi",
        ):
            (tmp_path / name).write_bytes(b"")
        assert list_input_video_files(str(tmp_path), ["vr4mice"]) == {
            "Xestia_2026-08-21_1": (
                str(tmp_path / "vr4mice_Xestia_2026-08-21_1_VIDEO2.avi"),
                str(tmp_path / "TS_vr4mice_Xestia_2026-08-21_1_CAMERA2.npy"),
            )
        }

    def test_missing_folder_gives_empty_dict(self, tmp_path):
        assert list_input_video_files(str(tmp_path / "absent"), ["vr4mice"]) == {}


class TestReadVideoFrame:
    @pytest.fixture
    def video(self, tmp_path):
        path = str(tmp_path / "small.avi")
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 10, (32, 24))
        for value in (0, 128, 255):
            writer.write(np.full((24, 32, 3), value, dtype=np.uint8))
        writer.release()
        return path

    def test_reads_requested_frame(self, video):
        frame = read_video_frame(video, 1)
        assert frame.shape == (24, 32, 3)
        assert abs(float(frame.mean()) - 128) < 5

    def test_out_of_bounds_raises(self, video):
        with pytest.raises(IndexError):
            read_video_frame(video, 3)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_video_frame(str(tmp_path / "absent.avi"), 0)


class _OffsetCapture:
    """Video of ``n_frames`` frames whose value is their index.

    Seeking to position ``p > 0`` lands on frame ``p + offset`` (H.264 in AVI);
    position 0 is exact, and a position past the last frame fails. Reading past
    the last frame fails, as for a real file.
    """

    def __init__(self, n_frames, offset):
        self.n_frames, self.offset, self.frame = n_frames, offset, 0

    def isOpened(self):
        return True

    def get(self, prop):
        assert prop == cv2.CAP_PROP_FRAME_COUNT
        return self.n_frames

    def set(self, prop, value):
        assert prop == cv2.CAP_PROP_POS_FRAMES
        if value >= self.n_frames:
            self.frame = self.n_frames
            return False
        self.frame = int(value) + self.offset if value > 0 else 0
        return True

    def grab(self):
        self.frame += 1
        return self.frame <= self.n_frames

    def read(self):
        if not 0 <= self.frame < self.n_frames:
            return False, None
        frame = np.full((4, 4, 3), self.frame, dtype=np.uint8)
        self.frame += 1
        return True, frame

    def release(self):
        pass


@pytest.mark.parametrize("offset", [-6, 0, 3])
@pytest.mark.parametrize("frame_index", [0, 2, 100, 193, 194, 199])
def test_read_video_frame_corrects_seeks_up_to_the_last_frame(
    monkeypatch, tmp_path, offset, frame_index
):
    # With offset -6, frame 199 used to seek to position 205, past the end.
    monkeypatch.setattr(cv2, "VideoCapture", lambda _: _OffsetCapture(200, offset))
    path = tmp_path / "video.avi"
    path.touch()

    frame = read_video_frame(str(path), frame_index, seek_offset=offset)

    assert frame[0, 0, 0] == frame_index


def test_find_scene_changes(tmp_path):
    path = str(tmp_path / "trials.avi")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 30, (100, 80))
    for i in range(80):
        frame = np.full((80, 100, 3), 90, dtype=np.uint8)
        if i >= 30:  # trial scene appears at frame 30, in the panel only
            frame[50:80, 0:40] = 200
        frame[0:10, 90:100] = 255 * (i % 2)  # sync square outside the panel
        writer.write(frame)
    writer.release()
    panel = (0, 40, 50, 40)
    assert find_scene_changes(path, panel, [24, 27]) == [30, 30]
    assert find_scene_changes(path, panel, [60]) == [None]  # no change near 60


def test_resize_frame_to_common_size():
    camera_panel = np.zeros((237, 316, 3), dtype=np.uint8)
    obs_panel = np.zeros((511, 926, 3), dtype=np.uint8)
    for panel in (camera_panel, obs_panel):
        assert resize_frame(panel, (948, 535)).shape == (535, 948, 3)


def test_crop_frame_takes_x_y_width_height():
    frame = np.arange(480 * 640 * 3).reshape(480, 640, 3)
    crop = crop_frame(frame, (0, 243, 316, 237))
    assert crop.shape == (237, 316, 3)
    np.testing.assert_array_equal(crop[0, 0], frame[243, 0])
    np.testing.assert_array_equal(crop[-1, -1], frame[479, 315])


def _sync_session(
    video_start=3.0,
    drift=1.0001,
    fps=60.0,
    duration=300.0,
    delay=0.06,
    invert_pd=False,
    dropped=(),
    seed=0,
    regular=False,
    pulse_start=0.0,
):
    """Synthetic session: random-interval sync square seen by photodiode and video.

    Game time 0 is the game start. The square turns on at the sync pulses and is
    seen by both the photodiode and the video ``delay`` s later. The video starts
    ``video_start`` s before game time 0 with clock ``drift``; frames listed in
    ``dropped`` are missing from the recording while timestamps stay frame / fps.
    ``regular`` uses a 0.4 s pulse train (batch1 "pulse") starting at ``pulse_start``.
    """
    rng = np.random.default_rng(seed)
    if regular:
        starts = pulse_start + np.arange(0, duration, 0.4)
    else:
        starts = pulse_start + np.cumsum(rng.uniform(0.23, 1.2, size=600))
    starts = starts[starts < duration]
    widths = np.diff(np.append(starts, duration)) / 2

    def square(game_t):
        k = np.searchsorted(starts, game_t - delay, side="right") - 1
        inside = (k >= 0) & (
            game_t - delay - starts[np.clip(k, 0, None)] < widths[np.clip(k, 0, None)]
        )
        return inside.astype(int)

    pd_t = np.arange(-5.0, duration + 5.0, 0.001)
    pd_read = np.where(square(pd_t) == 1, 440.0, 400.0) + rng.normal(0, 3, pd_t.size)
    if invert_pd:
        pd_read = 840.0 - pd_read
    pd_read[:100] = 280.0  # start-up transient, as in real PROC files
    photodiode_df = pd.DataFrame({"time_stamp": pd_t, "photodiode_read": pd_read})

    n_frames = int((duration + video_start) * fps)
    capture = np.arange(n_frames + len(dropped))
    capture = np.delete(capture, list(dropped))  # frames actually recorded
    capture_video_time = capture / fps  # true video-clock time of each frame
    game_t = (capture_video_time - video_start) / drift
    video_df = pd.DataFrame(
        {
            "frame_ids": np.arange(n_frames),
            "timestamps": np.arange(n_frames) / fps,  # frame / fps, as for OBS
            "signals": square(game_t[:n_frames]),
        }
    )
    step_times = np.arange(1.0, duration - 1.0, 0.05)
    # Frame captured at each step's game time (true capture times)
    true_frames = np.interp(
        video_start + drift * step_times,
        capture_video_time[:n_frames],
        np.arange(n_frames),
    )
    return video_df, photodiode_df, step_times, true_frames


class TestAlignByPhotodiode:
    def test_recovers_frames_with_unknown_start_and_drift(self):
        video_df, photodiode_df, steps, truth = _sync_session(video_start=7.3)
        frames, qa = align_steps_to_frames_by_photodiode(video_df, photodiode_df, steps)
        assert qa["drift"] == pytest.approx(1.0001, abs=1e-4)
        assert qa["pair_fraction"] > 0.95
        assert np.nanmax(np.abs(frames - truth)) <= 1.0

    def test_recording_started_long_before_the_game(self):
        # OBS started 90 s before the game: offsets beyond 60 s are searched
        video_df, photodiode_df, steps, truth = _sync_session(video_start=90.0)
        frames, qa = align_steps_to_frames_by_photodiode(video_df, photodiode_df, steps)
        assert qa["pair_fraction"] > 0.95
        assert np.nanmax(np.abs(frames - truth)) <= 1.0

    def test_inverted_photodiode_polarity_detected(self):
        video_df, photodiode_df, steps, truth = _sync_session(invert_pd=True)
        frames, qa = align_steps_to_frames_by_photodiode(video_df, photodiode_df, steps)
        assert qa["pd_invert"] == 1.0
        assert np.nanmax(np.abs(frames - truth)) <= 1.0

    def test_dropped_frames_followed_by_residual_correction(self):
        # single frames dropped every ~5 s, as OBS skips frames under load
        dropped = list(range(300, 18000, 307))
        video_df, photodiode_df, steps, truth = _sync_session(dropped=dropped)
        frames, _ = align_steps_to_frames_by_photodiode(video_df, photodiode_df, steps)
        err = np.abs(frames - truth)
        assert np.nanmedian(err) <= 1.0
        assert np.nanmax(err) <= 2.0

    def test_sudden_jump_fails_qa_instead_of_misaligning(self):
        dropped = list(range(9000, 9012))  # 12 frames (0.2 s) lost at once
        video_df, photodiode_df, steps, _ = _sync_session(dropped=dropped)
        with pytest.raises(ValueError, match="pair_fraction"):
            align_steps_to_frames_by_photodiode(video_df, photodiode_df, steps)

    def test_regular_pulses_anchored_on_first_edge(self):
        video_df, photodiode_df, steps, truth = _sync_session(
            regular=True, pulse_start=2.0, video_start=7.3
        )
        frames, qa = align_steps_to_frames_by_photodiode(
            video_df, photodiode_df, steps, regular_pulses=True
        )
        assert qa["pair_fraction"] > 0.95
        assert np.nanmax(np.abs(frames - truth)) <= 1.0

    @pytest.mark.parametrize("regular", [False, True])
    def test_generated_signal_stands_in_for_photodiode(self, regular):
        # No photodiode: the PROC's generated signal, one sample per DLC frame
        # (100 Hz), on only at the sample sending each pulse, at send time =
        # display time - delay; the fallback adds the display delay back.
        video_df, photodiode_df, steps, truth = _sync_session(
            regular=regular, pulse_start=2.0, video_start=7.3
        )
        display = np.round(photodiode_df["photodiode_read"].to_numpy()) > 420
        display_t = photodiode_df["time_stamp"].to_numpy()
        onsets = display_t[1:][display[1:] & ~display[:-1]]
        send_t = np.arange(-5.0, 300.0, 0.01)
        signal = np.zeros(send_t.size)
        signal[np.searchsorted(send_t, onsets - 0.06)] = 1.0
        generated_df = pd.DataFrame(
            {"time_stamp": send_t + 0.062, "photodiode_read": signal}
        )
        frames, qa = align_steps_to_frames_by_photodiode(
            video_df,
            generated_df,
            steps,
            regular_pulses=regular,
            pd_lowpass=False,
            pd_level_percentiles=(0, 100),
        )
        assert qa["pair_fraction"] > 0.95
        assert np.nanmax(np.abs(frames - truth)) <= 1.0
        # short pulses: the default percentile levels see a flat signal
        with pytest.raises(ValueError):
            align_steps_to_frames_by_photodiode(
                video_df, generated_df, steps, regular_pulses=regular
            )

    def test_regular_pulses_ignore_a_stray_flash_before_the_train(self):
        # A window flashes over the sync region 4 s (10 periods) before the
        # train: anchored on it, every frame would be 240 frames off while all
        # later edges still pair.
        video_df, photodiode_df, steps, truth = _sync_session(
            regular=True, pulse_start=2.0, video_start=7.3
        )
        game_time = video_df["timestamps"] / 1.0001 - 7.3
        flash = (game_time >= 2.06 - 4.0) & (game_time < 2.06 - 3.8)
        video_df.loc[flash, "signals"] = 1
        frames, qa = align_steps_to_frames_by_photodiode(
            video_df, photodiode_df, steps, regular_pulses=True
        )
        assert qa["pair_fraction"] > 0.95
        assert np.nanmax(np.abs(frames - truth)) <= 1.0

    def test_regular_pulses_recording_started_mid_train_fails(self):
        # video starts 10 s after game start, pulses from 2 s: first video edge
        # is a later pulse, which would shift every frame by whole periods
        video_df, photodiode_df, steps, _ = _sync_session(
            regular=True, pulse_start=2.0, video_start=-10.0
        )
        with pytest.raises(ValueError, match="quiet period"):
            align_steps_to_frames_by_photodiode(
                video_df, photodiode_df, steps, regular_pulses=True
            )

    def test_flat_photodiode_fails(self):
        video_df, photodiode_df, steps, _ = _sync_session()
        photodiode_df["photodiode_read"] = 400.0
        with pytest.raises(ValueError, match="QA failed"):
            align_steps_to_frames_by_photodiode(video_df, photodiode_df, steps)


class TestSyncSquare:
    SQUARE = (90, 40, 12, 10)  # x, y, w, h in a 100 x 80 frame
    STATES = [0, 1, 1, 0, 1, 0, 0, 1] * 10

    @pytest.fixture
    def video(self, tmp_path):
        path = str(tmp_path / "obs.avi")
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 30, (100, 80))
        x, y, w, h = self.SQUARE
        for state in self.STATES:
            frame = np.full((80, 100, 3), 120, dtype=np.uint8)  # grey screens
            frame[y : y + h, x : x + w] = 255 if state else 0
            writer.write(frame)
        writer.release()
        return path

    def test_finds_the_toggling_square(self, video):
        x, y, w, h = find_sync_square(video, search_region=(0.8, 0.3, 1.0, 0.8))
        sx, sy, sw, sh = self.SQUARE
        assert abs(x - sx) <= 1 and abs(y - sy) <= 1
        assert abs(w - sw) <= 2 and abs(h - sh) <= 2

    def test_trace_follows_the_square(self, video):
        trace = read_sync_trace(video, self.SQUARE)
        assert trace.dtype == np.uint8
        assert len(trace) == len(self.STATES)
        np.testing.assert_array_equal(binarize_sync_trace(trace), self.STATES)

    @pytest.mark.parametrize(
        ("size", "insets"), [((2, 2), (0, 0)), ((2, 9), (0, 3)), ((9, 2), (3, 0))]
    )
    def test_trace_clamps_inset_per_axis(self, monkeypatch, size, insets):
        x, y = 2, 3
        w, h = size
        inset_x, inset_y = insets
        frames = []
        for level in (0, 255):
            frame = np.full((16, 16, 3), 120, dtype=np.uint8)
            frame[y + inset_y : y + h - inset_y, x + inset_x : x + w - inset_x] = level
            frames.append((True, frame))
        capture = MagicMock()
        capture.read.side_effect = [*frames, (False, None)]
        monkeypatch.setattr(cv2, "VideoCapture", lambda _: capture)

        np.testing.assert_array_equal(
            read_sync_trace("obs.avi", (x, y, w, h)), [0, 255]
        )

    def test_trace_rejects_negative_inset(self):
        with pytest.raises(ValueError, match="inset must be nonnegative"):
            read_sync_trace("obs.avi", self.SQUARE, inset=-1)

    def test_no_square_raises(self, tmp_path):
        path = str(tmp_path / "flat.avi")
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 30, (100, 80))
        for _ in range(20):
            writer.write(np.full((80, 100, 3), 120, dtype=np.uint8))
        writer.release()
        with pytest.raises(ValueError, match="No sync square"):
            find_sync_square(path)


class TestAuditVideoFiles:
    KNOWN = ["Xestia_2026-08-21_1", "Jacana_2024-07-26_1", "Yurumi_2026-08-21_1"]

    def _issues(self, obs=(), camera=()):
        return {
            (folder, name): issue
            for folder, name, issue in audit_video_files(
                obs, camera, self.KNOWN, ["vr4mice", "Imagingsource"]
            )
        }

    def test_clean_folders_have_no_issue(self):
        assert not self._issues(
            obs=["Jacana_2024-07-26_1.mkv"],
            camera=[
                "vr4mice_Xestia_2026-08-21_1_VIDEO2.avi",
                "TS_vr4mice_Xestia_2026-08-21_1_CAMERA2.npy",
            ],
        )

    def test_session_not_ingested(self):
        issues = self._issues(
            obs=["Onager_2026-06-23_1.mp4"],
            camera=[
                "vr4mice_Tom_2026-08-21_1_VIDEO2.avi",
                "TS_vr4mice_Tom_2026-08-21_1_CAMERA2.npy",
            ],
        )
        assert len(issues) == 3
        assert all("not ingested" in i for i in issues.values())

    def test_half_pairs_other_cameras_and_bad_names(self):
        issues = self._issues(
            obs=["Jacana_2024-07-26 _1.mkv"],
            camera=[
                "vr4mice_Xestia_2026-08-21_1_VIDEO2.avi",
                "TS_vr4mice_Yurumi_2026-08-21_1_CAMERA2.npy",
                "vr4mice_Xestia_2026-08-21_1_VIDEO3.avi",
                "vr4mice_Xestia_2026-08-21_1_VIDEO2.avi.part",
                "other_Xestia_2026-08-21_1_VIDEO2.avi",
            ],
        )
        assert "unexpected name" in issues[("obs", "Jacana_2024-07-26 _1.mkv")]
        assert (
            "timestamps" in issues[("camera", "vr4mice_Xestia_2026-08-21_1_VIDEO2.avi")]
        )
        assert (
            "VIDEO2" in issues[("camera", "TS_vr4mice_Yurumi_2026-08-21_1_CAMERA2.npy")]
        )
        assert (
            "camera 3" in issues[("camera", "vr4mice_Xestia_2026-08-21_1_VIDEO3.avi")]
        )
        assert (
            "unexpected name"
            in issues[("camera", "vr4mice_Xestia_2026-08-21_1_VIDEO2.avi.part")]
        )
        assert "prefix" in issues[("camera", "other_Xestia_2026-08-21_1_VIDEO2.avi")]

    def test_session_with_both_setups(self):
        issues = self._issues(
            obs=["Xestia_2026-08-21_1.mp4"],
            camera=[
                "vr4mice_Xestia_2026-08-21_1_VIDEO2.avi",
                "TS_vr4mice_Xestia_2026-08-21_1_CAMERA2.npy",
            ],
        )
        assert "camera files" in issues[("obs", "Xestia_2026-08-21_1.mp4")]


class TestCheckCameraTimestamps:
    START = 1787301578.6  # 2026-08-21, as Xestia_2026-08-21_1

    def _ts(self, n=1000, dt=0.008):
        return self.START + np.arange(n) * dt

    def test_valid_session(self):
        assert check_camera_timestamps(self._ts(), "Xestia_2026-08-21_1") == []

    def test_another_days_timestamps(self):
        problems = check_camera_timestamps(self._ts(), "Xestia_2026-07-13_1")
        assert any("another session" in p for p in problems)

    def test_not_unix_times(self):
        problems = check_camera_timestamps(
            np.arange(1000) * 0.008, "Xestia_2026-08-21_1"
        )
        assert any("not unix" in p for p in problems)

    def test_gap_and_rate(self):
        ts = self._ts()
        ts[500:] += 5.0
        assert any(
            "without frames" in p
            for p in check_camera_timestamps(ts, "Xestia_2026-08-21_1")
        )
        slow = self._ts(dt=0.5)
        assert any(
            "frame interval" in p
            for p in check_camera_timestamps(slow, "Xestia_2026-08-21_1")
        )


def test_match_edge_times():
    pd_edges = np.array([1.0, 2.0, 3.5, 4.1])
    assert match_edge_times(pd_edges + 0.01, pd_edges)[0] == 1.0
    fraction, gap = match_edge_times(pd_edges + 0.3, pd_edges)
    assert fraction == 0.0 and gap == pytest.approx(0.3)


class TestVerifySyncAgainstPhotodiode:
    ROI = (90, 40, 12, 10)

    @pytest.fixture
    def session(self, tmp_path):
        rng = np.random.default_rng(3)
        fps_dt = 0.008
        n = 3000  # 24 s at 125 Hz
        frame_times = 1787301578.6 + np.arange(n) * fps_dt
        starts = frame_times[0] + np.cumsum(rng.uniform(0.23, 1.2, size=60))
        widths = np.append(np.diff(starts), 1.0) / 2

        def square(t):
            k = np.searchsorted(starts, t, side="right") - 1
            kk = np.clip(k, 0, None)
            return ((k >= 0) & (t - starts[kk] < widths[kk])).astype(int)

        path = str(tmp_path / "cam2.avi")
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 125, (100, 80))
        x, y, w, h = self.ROI
        for state in square(frame_times):
            frame = np.full((80, 100, 3), 120, dtype=np.uint8)
            frame[y : y + h, x : x + w] = 255 if state else 0
            writer.write(frame)
        writer.release()
        pd_time = np.arange(frame_times[0] - 2, frame_times[-1] + 2, 0.001)
        pd_read = np.where(square(pd_time) == 1, 440.0, 400.0) + rng.normal(
            0, 2, pd_time.size
        )
        return path, frame_times, pd_time, pd_read

    def test_matching_video_and_timestamps(self, session):
        path, frame_times, pd_time, pd_read = session
        check = verify_sync_against_photodiode(
            path, self.ROI, frame_times, pd_time, pd_read, window=600
        )
        assert check["n_edges"] > 10
        assert check["match_fraction"] > 0.9

    def test_wrong_timestamps_detected(self, session):
        path, frame_times, pd_time, pd_read = session
        check = verify_sync_against_photodiode(
            path, self.ROI, frame_times + 3.0, pd_time, pd_read, window=600
        )
        assert check["match_fraction"] < 0.5


def test_regular_pulses_from_another_session_rejected():
    # same regular train shape, but the video comes from a longer session
    video_df, _, steps, _ = _sync_session(regular=True, pulse_start=2.0, duration=400.0)
    _, photodiode_df, _, _ = _sync_session(
        regular=True, pulse_start=2.0, duration=300.0
    )
    with pytest.raises(ValueError, match="sync pulses in the video"):
        align_steps_to_frames_by_photodiode(
            video_df, photodiode_df, steps[steps < 290], regular_pulses=True
        )


class TestSeekOffset:
    @pytest.fixture
    def noise_video(self, tmp_path):
        """Random frames: each frame is unique, seeking in MJPG is exact."""
        rng = np.random.default_rng(0)
        path = str(tmp_path / "noise.avi")
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 30, (64, 48))
        frames = rng.integers(0, 255, size=(300, 48, 64, 3), dtype=np.uint8)
        for frame in frames:
            writer.write(frame)
        writer.release()
        return path

    def test_exact_seeking_measures_zero(self, noise_video):
        assert measure_seek_offset(noise_video, probes=(100, 200)) == 0

    def test_read_video_frame_applies_the_offset(self, noise_video):
        exact = read_video_frame(noise_video, 106)
        # a video whose seeks land 6 frames early is read 6 frames further
        corrected = read_video_frame(noise_video, 100, seek_offset=-6)
        np.testing.assert_array_equal(corrected, exact)

    def test_identical_frames_cannot_be_measured(self, tmp_path):
        path = str(tmp_path / "static.avi")
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 30, (64, 48))
        for _ in range(300):
            writer.write(np.full((48, 64, 3), 120, dtype=np.uint8))
        writer.release()
        with pytest.raises(ValueError, match="too alike"):
            measure_seek_offset(path, probes=(100, 200))


# ---------------------------------------------------------------------------
# Schema: alignment decisions run on synthetic recordings (no database)

_DATASET = "Testmouse_2026-07-30_1"
_START = 1_785_412_800.0  # 2026-07-30 12:00 UTC, the dataset's date
_PANEL = (0, 243, 316, 237)  # mouse-view panel of the camera-2 video


def _pulse_train(rng, seconds):
    """Irregular (pulse_geo-like) sync pulses: start and end times (s)."""
    starts = np.cumsum(rng.uniform(0.23, 1.2, size=400))
    starts = starts[starts < seconds - 0.5]
    return starts, starts + np.diff(np.append(starts, seconds)) / 2


def _is_on(starts, ends, t):
    k = np.searchsorted(starts, t, side="right") - 1
    return (k >= 0) & (t < ends[np.clip(k, 0, None)])


def _camera_session(tmp_path, *, seconds=30, fps=30, lag=2, seed=0):
    """3-camera recording: 640x480 video of the screens, timestamps, photodiode.

    One game step per frame, at the frame's time. ITI and trial alternate every
    second; each trial's scene (a bright block in the mouse-view panel) appears
    ``lag`` frames after its first step. The sync square follows irregular
    pulses, which the photodiode sees at the same times. A frame code in the
    top-left corner keeps every frame unique (seek offset measurement).
    """
    rng = np.random.default_rng(seed)
    n = seconds * fps
    frame_time = np.arange(n) / fps  # game time; the video starts at game time 0
    iti = (np.arange(n) // fps) % 2 == 0
    scene = np.zeros(n, dtype=bool)
    scene[lag:] = ~iti[:-lag]
    starts, ends = _pulse_train(rng, seconds)

    path = str(tmp_path / f"Cam_{_DATASET}_VIDEO2.avi")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), fps, (640, 480))
    for i in range(n):
        frame = np.full((480, 640, 3), 70, dtype=np.uint8)
        if scene[i]:
            frame[300:400, 50:250] = 210
        frame[210:260, 600:630] = 250 if _is_on(starts, ends, frame_time[i]) else 5
        for bit in range(11):  # frame code
            frame[0:16, 16 * bit : 16 * bit + 16] = 255 if i >> bit & 1 else 0
        writer.write(frame)
    writer.release()

    timestamps = _START + frame_time
    pd_time = _START + np.arange(-2.0, seconds + 2.0, 0.001)
    pd_read = 400.0 + 40.0 * _is_on(starts, ends, pd_time - _START)
    pd_read += rng.normal(0, 2, pd_read.size)
    return SimpleNamespace(
        path=path,
        fps=fps,
        lag=lag,
        timestamps=timestamps,
        step_time=frame_time,  # step i at frame i's time
        iti=iti.astype(float),
        pd_time=pd_time,
        pd_read=pd_read,
    )


class _FailedSessions:
    def __init__(self):
        self.entries = []

    def __call__(self):
        return self

    @staticmethod
    def should_skip(*args):
        return False

    def add_entry(self, dataset, table, message):
        self.entries.append((dataset, table, message))


def _camera_tables(video_schema, monkeypatch, session, *, photodiode=True):
    """Stand-ins for the tables StepVideoFrame reads, holding ``session``."""
    from inputs_videos import find_sync_square

    key = {"dataset": _DATASET}
    failures = _FailedSessions()
    monkeypatch.setattr(
        video_schema,
        "vr4mice",
        SimpleNamespace(
            FailedSession=failures,
            State=_Rows(
                {
                    **key,
                    "start_time": [_START],
                    "step": np.arange(len(session.step_time)),
                    "step_time": session.step_time,
                }
            ),
            MouseState=_Rows({**key, "iti": session.iti}),
            SignalsPhotodiode=_Rows(
                *(
                    [
                        {
                            **key,
                            "photodiode_time": session.pd_time,
                            "photodiode_read": session.pd_read,
                        }
                    ]
                    if photodiode
                    else []
                )
            ),
        ),
    )
    monkeypatch.setattr(
        video_schema,
        "InputVideo",
        _Rows(
            {
                **key,
                "video_path": session.path,
                "timestamps": session.timestamps,
                "visual_roi": _PANEL,
                "sync_roi": find_sync_square(session.path),
                "seek_offset": 0,
            }
        ),
    )
    return key, failures


class TestCameraAlignment:
    def test_steps_match_the_camera_timestamps_checked_by_the_photodiode(
        self, video_schema, monkeypatch, tmp_path
    ):
        session = _camera_session(tmp_path)
        key, _ = _camera_tables(video_schema, monkeypatch, session)
        row = video_schema.StepVideoFrame._align_camera(key, _START, session.step_time)

        assert row["align_method"] == "timestamps"
        assert row["sync_match_fraction"] > 0.95
        np.testing.assert_array_equal(row["frame_ids"], np.arange(len(session.iti)))
        np.testing.assert_allclose(row["step_video_time"], _START + session.step_time)

    def test_photodiode_of_another_session_is_rejected(
        self, video_schema, monkeypatch, tmp_path
    ):
        session = _camera_session(tmp_path)
        other = _camera_session(tmp_path / "other", seed=1)
        session.pd_read = other.pd_read  # another sync pulse train
        key, _ = _camera_tables(video_schema, monkeypatch, session)
        with pytest.raises(ValueError, match="match the photodiode"):
            video_schema.StepVideoFrame._align_camera(key, _START, session.step_time)

    def test_without_photodiode_the_video_is_not_checked(
        self, video_schema, monkeypatch, tmp_path
    ):
        session = _camera_session(tmp_path)
        key, _ = _camera_tables(video_schema, monkeypatch, session, photodiode=False)
        row = video_schema.StepVideoFrame._align_camera(key, _START, session.step_time)
        assert row["sync_match_fraction"] is None

    def test_make_stores_frames_shown_after_the_measured_display_lag(
        self, video_schema, monkeypatch, tmp_path
    ):
        session = _camera_session(tmp_path, lag=2)
        key, failures = _camera_tables(video_schema, monkeypatch, session)
        monkeypatch.setattr(
            video_schema.StepVideoFrame,
            "heading",
            SimpleNamespace(names=["step_video_time"]),
            raising=False,
        )
        inserted = []
        table = video_schema.StepVideoFrame()
        table.insert1 = inserted.append
        table.make(key)

        assert failures.entries == []
        (row,) = inserted
        n = len(session.iti)
        assert row["video_source"] == "camera"
        # The scene first shows on frame s + 2 and was absent on s + 1: the
        # switch is timed between them, 1.5 frames after the step
        assert row["display_lag"] == pytest.approx(1.5 / 30, abs=1e-5)
        assert row["display_lag_trials"] == 15  # every trial start
        np.testing.assert_array_equal(row["step_frame_ids"], np.arange(n))
        # Shown 2 frames later; the last 2 steps are shown after the video ends
        np.testing.assert_array_equal(row["frame_ids"], np.r_[np.arange(2, n), -1, -1])
        assert row["n_steps_outside_video"] == 2

    def test_make_records_a_video_from_another_session(
        self, video_schema, monkeypatch, tmp_path
    ):
        session = _camera_session(tmp_path)
        session.step_time = session.step_time + 3600  # steps an hour later
        key, failures = _camera_tables(
            video_schema, monkeypatch, session, photodiode=False
        )
        table = video_schema.StepVideoFrame()
        table.insert1 = lambda row: pytest.fail("misaligned session stored")
        table.make(key)
        ((dataset, name, message),) = failures.entries
        assert (dataset, name) == (_DATASET, "StepVideoFrame")


class TestVideoIngestion:
    def test_input_video_is_checked_and_its_sync_square_found(
        self, video_schema, monkeypatch, tmp_path
    ):
        session = _camera_session(tmp_path)
        stamps = tmp_path / f"TS_Cam_{_DATASET}_CAMERA2.npy"
        np.save(stamps, session.timestamps)
        failures = _FailedSessions()
        monkeypatch.setattr(
            video_schema, "vr4mice", SimpleNamespace(FailedSession=failures)
        )
        monkeypatch.setattr(
            video_schema,
            "input_video_files",
            lambda: {_DATASET: (session.path, str(stamps))},
        )
        inserted = []
        table = video_schema.InputVideo()
        table.insert1 = inserted.append
        table.make({"dataset": _DATASET})

        assert failures.entries == []
        (row,) = inserted
        assert (row["width"], row["height"], row["n_frames"]) == (640, 480, 900)
        x, y, w, h = row["sync_roi"]
        assert 595 <= x <= 605 and 205 <= y <= 215 and w >= 25 and h >= 45
        assert row["seek_offset"] == 0

        # Timestamps of another camera (other frame count): rejected
        np.save(stamps, session.timestamps[:-10])
        inserted.clear()
        table.make({"dataset": _DATASET})
        assert inserted == []
        assert "frames but the timestamps file has" in failures.entries[-1][2]

    def test_raw_video_sync_reads_the_square_in_every_frame(
        self, video_schema, monkeypatch, tmp_path
    ):
        session = _camera_session(tmp_path)
        failures = _FailedSessions()
        monkeypatch.setattr(
            video_schema, "vr4mice", SimpleNamespace(FailedSession=failures)
        )
        monkeypatch.setattr(
            video_schema,
            "RawVideo",
            _Rows({"dataset": _DATASET, "video_path": session.path}),
        )
        inserted = []
        table = video_schema.RawVideoSync()
        table.insert1 = inserted.append
        table.make({"dataset": _DATASET})

        assert failures.entries == []
        (row,) = inserted
        assert row["fps"] == pytest.approx(30)
        assert row["n_frames"] == 900
        on = _is_on(*_pulse_train(np.random.default_rng(0), 30), np.arange(900) / 30)
        np.testing.assert_array_equal(row["sync_trace"] > 128, on)


class TestObsAlignment:
    """_align_obs: photodiode, or the PROC's generated signal in its place."""

    def _tables(self, video_schema, monkeypatch, video_df, *, photodiode=None):
        key = {"dataset": _DATASET}
        monkeypatch.setattr(
            video_schema,
            "vr4mice",
            SimpleNamespace(
                SignalsPhotodiode=_Rows(
                    *([{**key, **photodiode}] if photodiode else [])
                ),
                DatasetBatch=_Rows({**key, "batch_name": "batch2"}),
            ),
        )
        monkeypatch.setattr(
            video_schema,
            "ObsVideoLayout",
            _Rows({"batch_name": "batch2", "visual_roi": (0, 545, 948, 535)}),
        )
        monkeypatch.setattr(
            video_schema, "RawVideo", _Rows({**key, "video_path": "obs.mkv"})
        )
        monkeypatch.setattr(
            video_schema,
            "RawVideoSync",
            _Rows(
                {
                    **key,
                    "fps": 60.0,
                    "sync_trace": 20 + 200 * video_df["signals"].to_numpy(),
                    "seek_offset": 0,
                }
            ),
        )
        return key

    def _proc(self, monkeypatch, send_time, signal, signal_type=None):
        """dlc.DLCProcessor holding one PROC file's generated signal."""

        class DLCProcessor:
            heading = SimpleNamespace(names=["time_stamp", "signal", "signal_type"])

            def __and__(self, _key):
                return self

            def fetch(self, *attributes, as_dict=True):
                row = {
                    "time_stamp": send_time,
                    "signal": signal,
                    "signal_type": signal_type,
                }
                return (
                    [{a: row[a] for a in attributes}] if send_time is not None else []
                )

        monkeypatch.setattr(
            sys.modules["vr4mice.schema"],
            "dlc",
            SimpleNamespace(DLCProcessor=DLCProcessor()),
            raising=False,
        )

    def test_photodiode_is_used_when_present(self, video_schema, monkeypatch):
        video_df, photodiode_df, steps, truth = _sync_session(video_start=7.3)
        key = self._tables(
            video_schema,
            monkeypatch,
            video_df,
            photodiode={
                "photodiode_time": _START + photodiode_df["time_stamp"].to_numpy(),
                "photodiode_read": photodiode_df["photodiode_read"].to_numpy(),
                "signal_type": "pulse_geo",
            },
        )
        row = video_schema.StepVideoFrame._align_obs(key, _START, steps)

        assert row["align_method"] == "photodiode"
        assert row["generated_signal_delay"] is None
        assert np.nanmax(np.abs(row["step_video_time"] * 60 - truth)) <= 1.0

    @pytest.mark.parametrize("regular", [False, True])
    def test_generated_signal_is_shifted_by_its_display_delay(
        self, video_schema, monkeypatch, regular
    ):
        # PROC sends each pulse GENERATED_SIGNAL_DISPLAY_DELAY before the screen
        # shows it: one 100 Hz sample on per pulse, unix send times. Without
        # the delay, or the clean-signal options, frames would be off.
        video_df, photodiode_df, steps, truth = _sync_session(
            regular=regular, pulse_start=2.0, video_start=7.3
        )
        display = np.round(photodiode_df["photodiode_read"].to_numpy()) > 420
        display_t = photodiode_df["time_stamp"].to_numpy()
        onsets = display_t[1:][display[1:] & ~display[:-1]] - 0.06  # square delay
        delay = video_schema.GENERATED_SIGNAL_DISPLAY_DELAY
        send_t = np.arange(-5.0, 300.0, 0.01)
        signal = np.zeros(send_t.size)
        signal[np.searchsorted(send_t, onsets - delay)] = 1.0
        self._proc(monkeypatch, _START + send_t, signal)  # signal type inferred
        key = self._tables(video_schema, monkeypatch, video_df)
        row = video_schema.StepVideoFrame._align_obs(key, _START, steps)

        assert row["align_method"] == "generated_signal"
        assert row["generated_signal_delay"] == delay
        assert (
            np.nanmax(np.abs(row["step_video_time"] * 60 - (truth + 0.06 * 60))) <= 1.0
        )


class TestLoadGeneratedSignal:
    def _proc(self, monkeypatch, *args, **kwargs):
        TestObsAlignment._proc(None, monkeypatch, *args, **kwargs)

    def _pulses(self, intervals):
        send_time = _START + np.arange(0, 60, 0.01)
        signal = np.zeros(send_time.size)
        onsets = np.cumsum(intervals)
        signal[np.searchsorted(send_time, _START + onsets[onsets < 59])] = 1
        return send_time, signal

    def test_signal_type_is_inferred_from_the_pulse_intervals(
        self, video_schema, monkeypatch
    ):
        rng = np.random.default_rng(0)
        self._proc(monkeypatch, *self._pulses(np.full(100, 0.4)))
        assert video_schema.load_generated_signal({})[2] == "pulse"
        self._proc(monkeypatch, *self._pulses(rng.uniform(0.23, 1.2, 100)))
        assert video_schema.load_generated_signal({})[2] == "pulse_geo"

    def test_stored_signal_type_is_used(self, video_schema, monkeypatch):
        send_time, signal = self._pulses(np.full(100, 0.4))
        self._proc(monkeypatch, send_time, signal, signal_type="pulse_geo")
        assert video_schema.load_generated_signal({})[2] == "pulse_geo"

    def test_missing_or_too_short_signal_fails(self, video_schema, monkeypatch):
        self._proc(monkeypatch, None, None)
        with pytest.raises(ValueError, match="no generated sync signal"):
            video_schema.load_generated_signal({})
        self._proc(monkeypatch, *self._pulses(np.full(5, 0.4)))
        with pytest.raises(ValueError, match="pulses only"):
            video_schema.load_generated_signal({})


class TestRawVideo:
    def _make(self, video_schema, monkeypatch, tmp_path):
        failures = _FailedSessions()
        monkeypatch.setattr(
            video_schema, "vr4mice", SimpleNamespace(FailedSession=failures)
        )
        monkeypatch.setattr(video_schema, "OBS_VIDEO_DIR", str(tmp_path))
        inserted = []
        table = video_schema.RawVideo()
        table.insert1 = inserted.append
        table.make({"dataset": _DATASET})
        return inserted, failures.entries

    def _video(self, path, size):
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 60, size)
        for _ in range(3):
            writer.write(np.zeros((size[1], size[0], 3), dtype=np.uint8))
        writer.release()

    def test_obs_recording_is_found_and_checked(
        self, video_schema, monkeypatch, tmp_path
    ):
        # No recording: not a failure, many sessions have none
        assert self._make(video_schema, monkeypatch, tmp_path) == ([], [])

        self._video(tmp_path / f"{_DATASET}.mp4", (1920, 1080))
        inserted, failures = self._make(video_schema, monkeypatch, tmp_path)
        assert failures == []
        assert inserted[0]["video_path"] == str(tmp_path / f"{_DATASET}.mp4")

    def test_recording_of_another_size_is_rejected(
        self, video_schema, monkeypatch, tmp_path
    ):
        self._video(tmp_path / f"{_DATASET}.mkv", (640, 480))
        inserted, failures = self._make(video_schema, monkeypatch, tmp_path)
        assert inserted == []
        assert "not an OBS recording" in failures[0][2]


class TestFrameVisibilityMake:
    """Session decisions of FrameVisibility.make, on the synthetic recording."""

    def _make(self, video_schema, monkeypatch, tmp_path, label, set_name, stage):
        session = _camera_session(tmp_path)
        key, failures = _camera_tables(video_schema, monkeypatch, session)
        monkeypatch.setattr(
            video_schema.StepVideoFrame,
            "heading",
            SimpleNamespace(names=["step_video_time"]),
            raising=False,
        )
        aligned = []
        steps = video_schema.StepVideoFrame()
        steps.insert1 = aligned.append
        steps.make(key)
        (row,) = aligned

        n = len(session.iti)
        trial = np.cumsum(np.r_[0, np.diff(session.iti) < 0])  # +1 at each start
        tables = video_schema.vr4mice
        tables.Dataset = _Rows({**key, "session_label": label})
        tables.State = _Rows({**key, "episode": trial, "occlusion_type": None})
        tables.MouseState = _Rows(
            {
                **key,
                "iti": session.iti,
                "x_pos": np.zeros(n),
                "z_pos": np.zeros(n),
                "obj_left": np.zeros(n),
            }
        )
        tables.GuiParams = _Rows()
        monkeypatch.setattr(video_schema, "StepVideoFrame", _Rows({**key, **row}))
        monkeypatch.setitem(
            sys.modules,
            "vr4mice.schema.decision",
            SimpleNamespace(
                SessionLabel=_Rows(
                    {"session_label": label, "set_name": set_name, "stage_name": stage}
                )
            ),
        )
        import frame_visibility

        monkeypatch.setitem(
            sys.modules, "vr4mice.analysis.frame_visibility", frame_visibility
        )
        inserted = []
        table = video_schema.FrameVisibility()
        table.insert1 = inserted.append
        table.make(key)
        assert failures.entries == []
        return session, inserted

    def test_white_target_is_counted_in_trials_only(
        self, video_schema, monkeypatch, tmp_path
    ):
        session, (row,) = self._make(
            video_schema,
            monkeypatch,
            tmp_path,
            "contrast_white_v1",
            "contrast_white_target",
            "dual",
        )
        d = row["descriptors"]
        # Each step's frame, 2 frames later, shows its own scene: the block
        # (100x200 px) in trial steps, nothing in ITI steps
        in_trial = session.iti[d["step_index"]] == 0
        assert np.all(np.abs(d["t_px"][in_trial] - 20000) < 100)
        assert (d["t_px"][~in_trial] == 0).all()
        assert (d["d_px"] == 0).all()
        assert row["calibration"]["status"] == "fitted"

    def test_white_object_is_the_distractor_of_a_black_target(
        self, video_schema, monkeypatch, tmp_path
    ):
        _, (row,) = self._make(
            video_schema,
            monkeypatch,
            tmp_path,
            "contrast_black_v1",
            "contrast_black_target",
            "dual",
        )
        d = row["descriptors"]
        assert (d["t_px"] == 0).all()
        assert d["d_px"].max() > 0

    def test_detection_task_has_no_distractor(
        self, video_schema, monkeypatch, tmp_path
    ):
        _, (row,) = self._make(
            video_schema,
            monkeypatch,
            tmp_path,
            "ar_det_black",
            "contrast_black_target",
            "dual",
        )
        assert (row["descriptors"]["d_px"] == 0).all()

    def test_unsupported_task_is_skipped(self, video_schema, monkeypatch, tmp_path):
        _, inserted = self._make(
            video_schema, monkeypatch, tmp_path, "foraging_v1", "foraging", "dual"
        )
        assert inserted == []


class TestPrecisionAndRobustness:
    def test_edges_are_timed_between_the_last_off_and_first_on_sample(self):
        from inputs_videos import _detect_edges

        frame_times = np.arange(10) / 30
        on = np.array([0, 0, 0, 1, 1, 0, 0, 1, 1, 1])
        # Switches between frames 2-3 and 6-7: half a frame before the first "on"
        np.testing.assert_allclose(_detect_edges(frame_times, on), [2.5 / 30, 6.5 / 30])

    def test_missing_photodiode_samples_do_not_hide_the_sync_edges(self):
        video_df, photodiode_df, steps, truth = _sync_session(video_start=7.3)
        photodiode_df.loc[5000:5100, "photodiode_read"] = np.nan  # dropout
        frames, qa = align_steps_to_frames_by_photodiode(video_df, photodiode_df, steps)
        assert qa["pair_fraction"] > 0.95
        assert np.nanmax(np.abs(frames - truth)) <= 1.0

    def test_seek_offset_of_a_video_too_short_to_probe(self, tmp_path):
        # Too few frames around the probes to compare positions: reported, not
        # an IndexError
        path = str(tmp_path / "short.avi")
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 30, (64, 48))
        for i in range(21):
            writer.write(np.full((48, 64, 3), i * 10, dtype=np.uint8))
        writer.release()
        with pytest.raises(ValueError, match="Could not measure seek accuracy"):
            measure_seek_offset(path, window=0, sequence=20)

    def test_audit_reports_a_video_and_timestamps_with_different_prefixes(self):
        dataset = "Xestia_2026-08-21_1"
        issues = audit_video_files(
            [],
            [
                f"Imagingsource_{dataset}_VIDEO2.avi",
                f"TS_vr4mice_{dataset}_CAMERA2.npy",
            ],
            [dataset],
            ["Imagingsource", "vr4mice"],
        )
        assert [
            (name.split("_")[0], "another prefix" in issue) for _, name, issue in issues
        ] == [
            ("Imagingsource", True),
            ("TS", True),
        ]

    def test_a_file_with_two_problems_keeps_both(
        self, video_schema, monkeypatch, tmp_path
    ):
        # VideoFileIssue holds one row per file: both problems in its issue
        camera, obs = tmp_path / "raw_input_videos", tmp_path / "raw_screen_recordings"
        camera.mkdir()
        obs.mkdir()
        dataset = "Xestia_2026-08-21_1"
        # OBS recording of a session not ingested, which also has camera files
        (obs / f"{dataset}.mkv").touch()
        (camera / f"Imagingsource_{dataset}_VIDEO2.avi").touch()
        (camera / f"TS_vr4mice_{dataset}_CAMERA2.npy").touch()
        (camera / f"TS_Imagingsource_{dataset}_CAMERA2.npy").touch()

        class VideoFileIssue:
            rows = []

            @classmethod
            def fetch(cls, *args):
                return []

            @classmethod
            def insert(cls, rows, replace=False):
                cls.rows = list(rows)

        monkeypatch.setattr(video_schema, "VideoFileIssue", VideoFileIssue)
        monkeypatch.setattr(
            video_schema,
            "vr4mice",
            SimpleNamespace(Dataset=SimpleNamespace(fetch=lambda *_: [])),
        )
        monkeypatch.setitem(
            sys.modules,
            "vr4mice.actions.populate_rig",
            SimpleNamespace(_img_src_candidates=lambda: ["Imagingsource", "vr4mice"]),
        )
        video_schema.check_video_files(str(obs), str(camera))

        rows = {r["file_name"]: r["issue"] for r in VideoFileIssue.rows}
        obs_issue = rows[f"{dataset}.mkv"]
        assert "no session" in obs_issue and "also has camera files" in obs_issue
        video_issue = rows[f"Imagingsource_{dataset}_VIDEO2.avi"]
        assert "no session" in video_issue  # not ingested
        stamps_issue = rows[f"TS_vr4mice_{dataset}_CAMERA2.npy"]
        assert "no ..._VIDEO2.avi" in stamps_issue
        assert len(VideoFileIssue.rows) == 4

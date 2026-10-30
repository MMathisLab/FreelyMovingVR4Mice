"""Unit tests for the 3-camera input video helpers in analysis/inputs_videos.py."""

import sys

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
    find_input_video_files,
    find_sync_square,
    list_input_video_files,
    read_sync_trace,
    read_video_frame,
    step_alignment_qa,
)

FRAME_TIMES = np.array([10.0, 10.1, 10.2, 10.3, 10.4])


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

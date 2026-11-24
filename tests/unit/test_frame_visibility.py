import numpy as np
import pytest

import frame_visibility as visibility


def _panel(*, white=False, black=False):
    panel = np.full((237, 316, 3), 90, dtype=np.uint8)
    if white:
        panel[70:88, 70:88] = 240
    if black:
        panel[80:96, 120:138] = 30
    return panel


def _describe(
    panels,
    frames,
    *,
    white_target=True,
    distractor=True,
    episodes=None,
    iti=None,
    pose=None,
    target_left=None,
    occluders=False,
    frame_workers=1,
):
    decoded = []

    def read_panels(frame_ids):
        for frame_id in frame_ids:
            decoded.append(frame_id)
            yield panels[frame_id]

    n_steps = len(frames)
    iti = np.zeros(n_steps, dtype=bool) if iti is None else np.asarray(iti)
    descriptors, calibration, fits = visibility.describe_steps(
        read_panels,
        frames,
        np.zeros(n_steps) if episodes is None else episodes,
        iti,
        np.zeros((n_steps, 2)) if pose is None else pose,
        np.zeros(n_steps, dtype=bool) if target_left is None else target_left,
        target_is_white=white_target,
        has_distractor=distractor,
        has_occluders=occluders,
        frame_workers=frame_workers,
    )
    expected = (set(np.asarray(frames)[~iti]) - {-1}) | set(
        calibration["frame_pairs"].ravel()
    )
    assert sorted(decoded) == sorted(expected)
    return descriptors, calibration, fits


def test_mapped_steps_and_contrast_polarity():
    # Two ITI frames (0, 1) before the trial calibrate the segmentation
    panels = {
        0: _panel(),
        1: _panel(),
        2: _panel(),
        4: _panel(white=True),
        7: _panel(black=True),
        9: _panel(white=True, black=True),
    }
    frames = [0, 1, -1, 2, 4, 4, 7, 9, -1]
    iti = [True, True] + [False] * 7
    regular, _, fits = _describe(panels, frames, iti=iti)
    inverted, _, _ = _describe(panels, frames, iti=iti, white_target=False)

    np.testing.assert_array_equal(regular["step_index"], [0, 1, 3, 4, 5, 6, 7])
    np.testing.assert_array_equal(regular["frame_id"], [0, 1, 2, 4, 4, 7, 9])
    np.testing.assert_array_equal(regular["t_px"], [0, 0, 0, 324, 324, 0, 324])
    np.testing.assert_array_equal(regular["d_px"], [0, 0, 0, 0, 0, 288, 288])
    np.testing.assert_array_equal(inverted["t_px"], regular["d_px"])
    np.testing.assert_array_equal(inverted["d_px"], regular["t_px"])
    np.testing.assert_array_equal(
        inverted["total_visible_px"], regular["total_visible_px"]
    )
    np.testing.assert_array_equal(
        regular["visibility_state"],
        ["neither"] * 3 + ["target_only", "target_only", "distractor_only", "both"],
    )
    np.testing.assert_array_equal(
        inverted["visibility_state"],
        ["neither"] * 3 + ["distractor_only", "distractor_only", "target_only", "both"],
    )
    assert fits["t_new_surf"]["target_right"]["status"] == "insufficient_trials"
    assert np.isnan(regular["t_new_surf"]).all()


def test_target_only_zeroes_iti_even_if_it_shares_an_active_frame():
    # ITI frames 0 and 1 calibrate; the last ITI step shares frame 2
    panels = {0: _panel(), 1: _panel(), 2: _panel(white=True, black=True)}
    result, _, fits = _describe(
        panels,
        [0, 1, 2, 2],
        white_target=False,
        distractor=False,
        iti=[True, True, True, False],
    )

    np.testing.assert_array_equal(result["t_px"], [0, 0, 0, 288])
    np.testing.assert_array_equal(result["d_px"], [0, 0, 0, 0])
    np.testing.assert_array_equal(
        result["visibility_state"], ["neither"] * 3 + ["target_only"]
    )
    np.testing.assert_array_equal(result["d_new_surf"], [np.nan] * 3 + [0])
    assert fits["d_new_surf"]["status"] == "absent"


def test_iti_frames_are_decoded_only_for_calibration_and_never_segmented(monkeypatch):
    frames = [0, 0, 1, 2, 4, 4, 6, 8, 9, 11, 12, 15]
    iti = [True] * 4 + [False] * 3 + [True] * 2 + [False] * 3
    panels = {frame: _panel(white=not is_iti) for frame, is_iti in zip(frames, iti)}
    ids = {id(panel): frame for frame, panel in panels.items()}
    segmented = []
    segment_frame = visibility.segment_frame

    def track_segmentation(panel, *args, **kwargs):
        segmented.append(ids[id(panel)])
        return segment_frame(panel, *args, **kwargs)

    monkeypatch.setattr(visibility, "segment_frame", track_segmentation)
    result, calibration, _ = _describe(
        panels, frames, episodes=[0] * 7 + [1] * 5, iti=iti
    )
    np.testing.assert_array_equal(calibration["frame_pairs"], [[1, 6], [8, 12]])
    assert segmented == [4, 6, 11, 12, 15]
    assert np.all(result["total_visible_px"][iti] == 0)


def test_all_iti_steps_never_open_the_video():
    result, _, _ = _describe({}, [0, 1], iti=[True, True])
    np.testing.assert_array_equal(result["visibility_state"], ["neither", "neither"])


def test_parallel_frame_workers_match_serial_results():
    # ITI frames 0 and 1 (no objects) calibrate
    panels = {
        i: _panel(white=i > 1 and i % 2 == 0, black=i > 1 and i % 3 == 0)
        for i in range(12)
    }
    frames = [0, 1, -1, *range(2, 12), 11]
    iti = [True, True] + [False] * 12
    serial, _, _ = _describe(panels, frames, iti=iti)
    parallel, _, _ = _describe(panels, frames, iti=iti, frame_workers=2)
    for name, values in serial.items():
        np.testing.assert_array_equal(parallel[name], values)


def test_novelty_resets_and_is_counted_once_per_frame(monkeypatch):
    def fit(pose, observations, episodes):
        if not len(pose):
            return {"status": "insufficient_trials"}
        _, x, y, width, height = observations[0]
        if x > 100:
            width *= 2
        return {
            "status": "fitted",
            "degree": 1,
            "pose_center": np.zeros(2),
            "pose_scale": np.ones(2),
            "coefficients": np.array([[0, x, y, width, height], [0] * 5, [0] * 5]),
        }

    monkeypatch.setattr(visibility, "_fit_silhouette", fit)
    # ITI frames 0 and 1 calibrate; the last ITI step shares frame 2
    panels = {0: _panel(), 1: _panel()}
    panels.update({i: _panel(white=True, black=True) for i in range(2, 5)})
    options = dict(episodes=[0, 0, 0, 0, 0, 0, 1, 1], iti=[True] * 3 + [False] * 5)
    frames = [0, 1, 2, 2, 2, 3, 3, 4]
    regular, _, _ = _describe(panels, frames, **options)
    inverted, _, _ = _describe(panels, frames, white_target=False, **options)

    np.testing.assert_array_equal(regular["t_new_surf"], [np.nan] * 3 + [1, 0, 0, 1, 0])
    distractor_reveal = regular["d_new_surf"][3]
    assert 0 < distractor_reveal < 1
    np.testing.assert_array_equal(
        regular["d_new_surf"],
        [np.nan] * 3 + [distractor_reveal, 0, 0, distractor_reveal, 0],
    )
    np.testing.assert_array_equal(inverted["t_new_surf"], regular["d_new_surf"])
    np.testing.assert_array_equal(inverted["d_new_surf"], regular["t_new_surf"])


def test_unoccluded_fit_uses_pose_and_handles_insufficient_support():
    rng = np.random.default_rng(8)
    pose = rng.normal(size=(70, 2))
    episodes = np.repeat(np.arange(7), 10)
    x, z = pose.T
    observations = np.column_stack((x**2 - z, x + 50, z + 40, x * 0 + 20, z + 30))
    fit = visibility._fit_silhouette(pose, observations, episodes)
    assert fit["status"] == "fitted"
    np.testing.assert_allclose(
        visibility._poly_features(
            (pose - fit["pose_center"]) / fit["pose_scale"], fit["degree"]
        )
        @ fit["coefficients"],
        observations,
        atol=1e-9,
    )
    assert (
        visibility._fit_silhouette(np.zeros_like(pose), observations, episodes)[
            "status"
        ]
        == "insufficient_pose_support"
    )


def test_silhouette_models_distinguish_target_sides_at_the_same_pose():
    rng = np.random.default_rng(4)
    pose = rng.normal(size=(40, 2))
    episodes = np.repeat(np.arange(8), 5)
    x, z = pose.T
    observations = np.column_stack((x + z, 80 + x, 110 + z, 45 + x, 50 + z))
    other_side = observations.copy()
    other_side[:, 1] += 140
    boxes, fits = visibility._predict_silhouettes(
        np.vstack((pose, pose, pose[:1])),
        np.vstack((observations, other_side, np.full((1, 5), np.nan))),
        np.r_[episodes, episodes + 8, 16],
        np.r_[np.ones(40), np.zeros(40), np.nan],
    )
    assert all(fit["status"] == "fitted" for fit in fits.values())
    np.testing.assert_allclose(boxes[:40], observations[:, 1:])
    np.testing.assert_allclose(boxes[40:80], other_side[:, 1:])
    assert np.isnan(boxes[80]).all()


def test_visible_mask_outside_silhouette_is_missing_and_preserves_novelty():
    mask = _panel(white=True)[:, :, 0] > 200
    boxes = np.array([[220, 78.5, 18, 18], *([[78.5, 78.5, 18, 18]] * 3)])
    values = visibility.surface_novelty(
        [mask, mask, mask, np.zeros_like(mask)], boxes, [1, 1, 1, 1]
    )
    np.testing.assert_array_equal(values, [np.nan, 1.0, 0.0, 0.0])


def test_no_mapped_steps_needs_no_video():
    result, _, _ = _describe({}, [-1, -1])
    assert all(column.size == 0 for column in result.values())


def _arena(*, white=False, black=False):
    """Panel with structure: sky, floor band, occluder slab, objects.

    Sky (grey 90) down to row 187, a brighter floor (150) below. An occluder
    slab: front face (33, 35, 37) in columns 150-179 and a side face
    (40, 40, 44) in columns 180-185, rows 40-169. ``white``: a white object
    (240) in rows 80-129, columns 120-169, half behind the slab. ``black``: a
    black object (20) standing on the floor, rows 100-187, columns 40-80, with
    a shaded rim (120) in the floor band, rows 188-198, not dark itself.
    """
    panel = np.full((237, 316, 3), 90, dtype=np.uint8)
    panel[188:] = 150
    if white:
        panel[80:130, 120:170] = 240
    if black:
        panel[100:188, 40:81] = 20
        panel[188:199, 40:81] = 120
    panel[40:170, 150:180] = (33, 35, 37)
    panel[40:170, 180:186] = (40, 40, 44)
    return panel


def test_calibration_finds_dark_threshold_floor_and_slab_colours():
    params = visibility.fit_session_params(
        [_arena()] * 2, [_arena(white=True, black=True)], has_occluders=True
    )
    # dark threshold from the histogram valley, between slab faces and sky
    assert params["t_dark"] != visibility.DEFAULT_PARAMS["t_dark"]
    assert 41 < params["t_dark"] < 90
    assert params["y_floor"] == 188
    assert params["t_white"] == pytest.approx(1.1 * 90)
    assert params["t_white_floor"] == pytest.approx(1.05 * 150)
    assert params["band_dev_thr"] is not None
    assert params["front_color"] == [33, 35, 37]
    assert params["face_palette"] == [[40, 40, 44]]


def test_occluder_is_not_counted_as_object_and_hides_the_white_one():
    params = visibility.fit_session_params(
        [_arena()] * 2, [_arena(white=True, black=True)], has_occluders=True
    )
    labels = visibility.segment_frame(
        _arena(white=True, black=True), params, has_occluders=True
    )
    counts = {
        name: int((labels == value).sum())
        for name, value in [
            ("white", visibility.WHITE),
            ("black", visibility.BLACK),
            ("occluder", visibility.OCCLUDER),
        ]
    }
    assert counts["occluder"] == 130 * (30 + 6)  # front and side faces
    assert counts["white"] == 50 * 30  # the half in front of the slab
    # body, plus its shaded rim recovered by floor-band growth
    assert counts["black"] == 88 * 41 + 11 * 41

    # Without occluder detection, the dark slab is taken for a black object
    unoccluded = visibility.segment_frame(
        _arena(white=True, black=True), params, has_occluders=False
    )
    assert (unoccluded == visibility.BLACK).sum() > counts["black"] + 130 * 30


def test_shaded_rim_needs_floor_band_growth():
    params = visibility.fit_session_params(
        [_arena()] * 2, [_arena(black=True)], has_occluders=True
    )
    params["band_dev_thr"] = None  # no growth
    labels = visibility.segment_frame(_arena(black=True), params, has_occluders=True)
    assert (labels == visibility.BLACK).sum() == 88 * 41


def test_white_threshold_is_fitted_on_the_iti_background():
    params = visibility.fit_session_params([_panel()], [_panel(white=True)])
    assert params["t_white"] == pytest.approx(1.1 * 90)


def test_unreachable_white_threshold_fails_instead_of_counting_nothing():
    # One background pixel at 235 would put the threshold at 258 (> 255)
    bright_pixel = _panel()
    bright_pixel[10, 10] = 235
    with pytest.raises(ValueError, match="t_white 258 is above 255"):
        visibility.fit_session_params([bright_pixel], [_panel(white=True)])


def test_iti_frames_all_showing_an_object_fail_calibration():
    # The threshold then comes from the object (240): 264, above 255
    with pytest.raises(ValueError, match="t_white 264 is above 255"):
        visibility.fit_session_params(
            [_panel(white=True), _panel(white=True)], [_panel(white=True)]
        )


def test_session_without_iti_before_its_trials_fails():
    # Active frames but no ITI to calibrate the segmentation on
    with pytest.raises(ValueError, match="cannot calibrate"):
        _describe({0: _panel(white=True), 1: _panel()}, [0, 1])


def test_truncated_reader_fails_session():
    with pytest.raises(ValueError, match="shorter"):
        visibility.describe_steps(
            lambda _: iter(()),
            [0, 1, 2],
            [0, 0, 0],
            [True, True, False],
            np.zeros((3, 2)),
            [False] * 3,
            target_is_white=True,
            has_distractor=True,
            has_occluders=True,
        )


def _shown_frames(frame_ids):
    # Steps 0, 1, 2 and 4 shown on frames ``frame_ids`` of a 20 fps video; step
    # 3 has no displayed frame (outside the video).
    descriptors = {
        "step_index": np.array([0, 1, 2, 4]),
        "frame_id": np.array(frame_ids),
        "t_px": np.array([1.0, 2.0, 4.0, 8.0]),
    }
    return descriptors, np.arange(10) * 0.05


def test_visibility_takes_the_last_frame_captured_by_the_query_time():
    # Frames captured at 0.05, 0.15, 0.25 and 0.45 s (video clock); step 2's
    # frame is held until step 4's.
    descriptors, frame_times = _shown_frames([1, 3, 5, 9])
    values = visibility.visibility_at_times(
        descriptors,
        frame_times,
        [0.0, 0.05, 0.1, 0.16, 0.3, 0.44, 0.46],
        max_gap=0.25,
        columns=("t_px",),
    )

    np.testing.assert_array_equal(
        values["t_px"], [np.nan, 1.0, 1.0, 2.0, 4.0, 4.0, 8.0]
    )


def test_visibility_is_missing_where_no_frame_is_held():
    # Frames captured at 0, 0.1, 0.2 and 0.4 s. At 0.35 s step 2's frame is
    # held 0.15 s, longer than max_gap, and after the last frame queries are
    # also too far.
    descriptors, frame_times = _shown_frames([0, 2, 4, 8])
    values = visibility.visibility_at_times(
        descriptors,
        frame_times,
        [0.25, 0.35, 0.4, 1.0, np.nan],
        max_gap=0.1,
        columns=("t_px",),
    )

    np.testing.assert_array_equal(values["t_px"], [4.0, np.nan, 8.0, np.nan, np.nan])


def test_a_frame_is_not_shown_before_it_is_captured():
    # 30 fps: the scene's frame 11 is captured at 0.367 s, so at 0.35 s the
    # screen still shows frame 10. Steps 2 and 3 share frame 11, which shows
    # the later one.
    descriptors = {
        "step_index": np.array([1, 2, 3]),
        "frame_id": np.array([10, 11, 11]),
        "t_px": np.array([0.0, 5.0, 6.0]),
    }
    values = visibility.visibility_at_times(
        descriptors,
        np.arange(20) / 30,
        [0.35, 0.37],
        columns=("frame_id", "step_index", "t_px"),
    )

    np.testing.assert_array_equal(values["frame_id"], [10, 11])
    np.testing.assert_array_equal(values["step_index"], [1, 3])
    np.testing.assert_array_equal(values["t_px"], [0.0, 6.0])


def _scene():
    # Steps every 0.1 s: ITI at steps 0-1 and 5, trials start at steps 2 and 6.
    step_times = np.arange(9) * 0.1
    iti = np.array([1, 1, 0, 0, 0, 1, 0, 0, 0])
    return step_times, iti, np.array([2, 6])


def test_scene_is_shown_from_the_trial_onset_frame():
    step_times, iti, starts = _scene()
    # Queries in trial 1 (from 0.2 s) and trial 2 (from 0.6 s). Trial 1's scene
    # reaches the video at frame 31, one frame after its first step's frame
    # (30); trial 2's onset is unknown, so its first step's frame counts.
    query = [0.25, 0.35, 0.45, 0.65, 0.75]
    frames = [30, 31, 32, 60, 61]
    steps = [1, 2, 3, 5, 6]  # first query of each trial still shows the ITI
    shown = visibility.trial_scene_shown(
        query, frames, steps, step_times, iti, starts, [31, -1]
    )
    np.testing.assert_array_equal(shown, [False, True, True, False, True])

    # The first active step's frame is before the onset: previous scene
    shown = visibility.trial_scene_shown(
        [0.35, 0.45], [30, 31], [2, 3], step_times, iti, starts, [31, -1]
    )
    np.testing.assert_array_equal(shown, [False, True])


def test_scene_is_not_shown_without_a_frame_or_before_any_trial():
    step_times, iti, starts = _scene()
    shown = visibility.trial_scene_shown(
        [0.05, 0.35, np.nan],
        [10, np.nan, 40],
        [0, np.nan, 3],
        step_times,
        iti,
        starts,
        [-1, -1],
    )
    np.testing.assert_array_equal(shown, [False, False, False])
    assert not visibility.trial_scene_shown(
        [0.35], [30], [3], step_times, iti, [], []
    ).any()

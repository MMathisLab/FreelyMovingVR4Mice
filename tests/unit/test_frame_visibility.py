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
    panels = {
        2: _panel(),
        4: _panel(white=True),
        7: _panel(black=True),
        9: _panel(white=True, black=True),
    }
    frames = [-1, 2, 4, 4, 7, 9, -1]
    regular, _, fits = _describe(panels, frames)
    inverted, _, _ = _describe(panels, frames, white_target=False)

    np.testing.assert_array_equal(regular["step_index"], [1, 2, 3, 4, 5])
    np.testing.assert_array_equal(regular["frame_id"], [2, 4, 4, 7, 9])
    np.testing.assert_array_equal(regular["t_px"], [0, 324, 324, 0, 324])
    np.testing.assert_array_equal(regular["d_px"], [0, 0, 0, 288, 288])
    np.testing.assert_array_equal(inverted["t_px"], regular["d_px"])
    np.testing.assert_array_equal(inverted["d_px"], regular["t_px"])
    np.testing.assert_array_equal(
        inverted["total_visible_px"], regular["total_visible_px"]
    )
    np.testing.assert_array_equal(
        regular["visibility_state"],
        ["neither", "target_only", "target_only", "distractor_only", "both"],
    )
    np.testing.assert_array_equal(
        inverted["visibility_state"],
        ["neither", "distractor_only", "distractor_only", "target_only", "both"],
    )
    assert fits["t_new_surf"]["target_right"]["status"] == "insufficient_trials"
    assert np.isnan(regular["t_new_surf"]).all()


def test_target_only_zeroes_iti_even_if_it_shares_an_active_frame():
    panels = {0: _panel(white=True, black=True)}
    result, _, fits = _describe(
        panels, [0, 0], white_target=False, distractor=False, iti=[True, False]
    )

    np.testing.assert_array_equal(result["t_px"], [0, 288])
    np.testing.assert_array_equal(result["d_px"], [0, 0])
    np.testing.assert_array_equal(
        result["visibility_state"], ["neither", "target_only"]
    )
    np.testing.assert_array_equal(result["d_new_surf"], [np.nan, 0])
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
    panels = {i: _panel(white=i % 2 == 0, black=i % 3 == 0) for i in range(10)}
    frames = [-1, *range(10), 9]
    serial, _, _ = _describe(panels, frames)
    parallel, _, _ = _describe(panels, frames, frame_workers=2)
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
    panels = {i: _panel(white=True, black=True) for i in range(3)}
    options = dict(
        episodes=[0, 0, 0, 0, 1, 1], iti=[True, False, False, False, False, False]
    )
    frames = [0, 0, 0, 1, 1, 2]
    regular, _, _ = _describe(panels, frames, **options)
    inverted, _, _ = _describe(panels, frames, white_target=False, **options)

    np.testing.assert_array_equal(regular["t_new_surf"], [np.nan, 1, 0, 0, 1, 0])
    distractor_reveal = regular["d_new_surf"][1]
    assert 0 < distractor_reveal < 1
    np.testing.assert_array_equal(
        regular["d_new_surf"], [np.nan, distractor_reveal, 0, 0, distractor_reveal, 0]
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


def test_truncated_reader_fails_session():
    with pytest.raises(ValueError, match="shorter"):
        visibility.describe_steps(
            lambda _: iter(()),
            [0],
            [0],
            [False],
            [[0, 0]],
            [False],
            target_is_white=True,
            has_distractor=True,
            has_occluders=True,
        )


def test_trial_progress_places_active_steps_on_the_interpolation_grid():
    descriptors = {
        "step_index": np.array([0, 1, 2, 3, 4, 5, 7]),
        "t_px": np.array([1.0, 2.0, 4.0, 8.0, 100.0, 10.0, 30.0]),
    }
    episodes = [1, 1, 1, 1, 1, 2, 2, 2]
    times = [0.0, 1.0, 2.0, 3.0, 4.0, 10.0, 11.0, 12.0]
    iti = [0, 0, 0, 0, 1, 0, 0, 0]

    # Trial 1 spans 0-3 s (the ITI step at 4 s is excluded); trial 2 spans
    # 10-12 s although its middle step has no displayed frame.
    progress = visibility.visibility_by_trial_progress(
        descriptors, episodes, times, iti, n_points=3, columns=("t_px",)
    )

    assert progress["trial"].tolist() == [1, 1, 1, 2, 2]
    assert progress["trial_step"].tolist() == [0, 1, 2, 0, 2]
    assert progress["n_steps"].tolist() == [1, 2, 1, 1, 1]
    assert progress["t_px"].tolist() == [1.0, 3.0, 8.0, 10.0, 30.0]


def test_trial_progress_requires_aligned_step_arrays():
    with pytest.raises(ValueError, match="align"):
        visibility.visibility_by_trial_progress(
            {"step_index": np.array([0])}, [1, 1], [0.0], [0, 0]
        )

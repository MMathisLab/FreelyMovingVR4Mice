"""Step-aligned visibility on the 316 × 237 mouse-view panel.

Contrast segmentation.
Only pixel counts, categorical visibility and object-aligned surface novelty leave
this module. Frame alignment and database access belong to the caller.
"""

import zlib
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from contextlib import closing
from functools import lru_cache, partial
from itertools import combinations_with_replacement, groupby, islice
from multiprocessing import current_process, get_context
from operator import index

import numpy as np
from scipy import ndimage as ndi

PANEL_SIZE = (316, 237)
SURFACE_GRID = 16
BACKGROUND, WHITE, BLACK, OCCLUDER = 0, 1, 2, 3
_EIGHT = np.ones((3, 3), bool)

DEFAULT_PARAMS = {
    "t_dark": 43.0,  # luminance below which a pixel is occluder or black object
    "t_white": 156.0,  # luminance at/above which a pixel is a white-object candidate
    "y_floor": 188,  # rows >= this are the horizon/floor strip: a higher white threshold applies there
    "t_white_floor": 225.0,  # white threshold inside the floor strip (objects stand on it; it is brighter)
    "front_color": [
        33,
        35,
        37,
    ],  # occluder front face (modal dark colour of object-free frames)
    "front_tol": 2,  # per-channel tolerance around front_color for the occluder core
    "front_tol_ext": 4,  # looser tolerance (slab shade gradient 33,35,37 -> 36,38,39), but only in
    "ext_run_frac": 0.9,  # ... columns where the match spans >= this fraction of the core's height
    "face_palette": [],  # occluder side-face colours seen in object-free frames
    "face_tol": 1,
    "face_reach": 8,  # side faces count only within this many columns of a front-face core
    "min_run": 10,  # occluder: vertical run length (px)
    "min_core_area": 200,  # occluder front-face components below this are discarded
    "min_core_height": 40,  # ... and so are components shorter than this (slabs span ~130 rows)
    "min_area_black": 4,
    "min_area_white": 4,
    "max_white_components": 2,
    "band_dev_thr": None,  # per-session |pixel - row background| threshold in the floor band: a scalar or one value per band row (None = no band growth)
    "band_excl_margin": 2,  # columns around an object excluded from its row-background median
    "band_min_cols": 8,  # fewer bare columns than this in a band row -> no background estimate -> no growth there
    "band_margin": 8,  # band growth is limited to the object's column span +- this many px
    "band_anchor_rows": 3,  # seed pixels within this many rows above the band start anchor the growth
}


def luminance(rgb: np.ndarray) -> np.ndarray:
    """Average the RGB channels without gamma correction.

    Args:
        rgb: Image with shape ``(height, width, 3)`` and values from 0 to 255.

    Returns:
        Float array of mean channel values with shape ``(height, width)``.
    """
    return np.asarray(rgb, dtype=float).mean(axis=2)


def _keep_vertical_runs(mask: np.ndarray, min_run: int) -> np.ndarray:
    """Keep pixels in sufficiently long vertical runs.

    Args:
        mask: Boolean image containing candidate pixels.
        min_run: Minimum number of consecutive true pixels in one column.

    Returns:
        Boolean mask of pixels in qualifying runs.
    """
    h, w = mask.shape
    up = np.zeros((h, w), np.int32)
    run = np.zeros(w, np.int32)
    for y in range(h):
        run = np.where(mask[y], run + 1, 0)
        up[y] = run
    down = np.zeros((h, w), np.int32)
    run = np.zeros(w, np.int32)
    for y in range(h - 1, -1, -1):
        run = np.where(mask[y], run + 1, 0)
        down[y] = run
    return mask & (up + down - 1 >= min_run)


def _largest_components(mask: np.ndarray, k: int | None, min_area: int) -> np.ndarray:
    """Keep the largest qualifying 8-connected components.

    Args:
        mask: Boolean image to label.
        k: Maximum number of components to keep, or None to keep all qualifying ones.
        min_area: Minimum component size in pixels.

    Returns:
        Boolean mask of the retained components.
    """
    lab, n = ndi.label(mask, structure=_EIGHT)
    if n == 0:
        return np.zeros_like(mask)
    sizes = ndi.sum(mask, lab, index=np.arange(1, n + 1))
    order = np.argsort(-sizes, kind="stable")[:k]
    keep = [i + 1 for i in order if sizes[i] >= min_area]
    return np.isin(lab, keep)


def _row_background(
    rgb: np.ndarray, exclude: np.ndarray, row0: int, min_cols: int = 20
) -> np.ndarray:
    """Estimate background colors by row.

    Args:
        rgb: RGB image.
        exclude: Boolean mask of pixels to omit from the row medians.
        row0: Index of the first row to estimate.
        min_cols: Minimum number of usable columns for a row estimate.

    Returns:
        RGB medians with shape ``(height - row0, 3)``. Rows with too few usable
        columns inherit the previous estimate or contain NaN before the first one.
    """
    h = rgb.shape[0]
    out = np.full((h - row0, 3), np.nan)
    for i, r in enumerate(range(row0, h)):
        ok = ~exclude[r]
        if ok.sum() >= min_cols:
            out[i] = np.median(rgb[r][ok], axis=0)
        elif i > 0:
            out[i] = out[i - 1]
    return out


def _grow_in_band(seed, rgb, exclude_bg, forbid, p):
    """Recover shaded object pixels connected to the seed near the floor.

    The search starts at the floor-band boundary and is limited to columns near
    the anchor pixels. Hole filling recovers object interiors that resemble the
    background.

    Args:
        seed: Boolean object mask before floor-band growth.
        rgb: RGB image.
        exclude_bg: Pixels excluded from the background estimate.
        forbid: Pixels that cannot be added to the object.
        p: Segmentation parameters, including band limits and deviation thresholds.

    Returns:
        Boolean object mask with any recovered floor-band pixels included.
    """
    y0 = int(p["y_floor"])
    h, w = seed.shape
    thr = p["band_dev_thr"]
    if thr is None or y0 >= h or not seed.any():
        return seed
    anchor = seed.copy()
    anchor[: max(y0 - int(p["band_anchor_rows"]), 0)] = False
    anchor[y0 + 1 :] = False
    if not anchor.any():
        return seed
    cols = np.nonzero(anchor.any(axis=0))[0]
    lo, hi = max(cols.min() - int(p["band_margin"]), 0), min(
        cols.max() + int(p["band_margin"]), w - 1
    )
    bg = _row_background(rgb, exclude_bg, y0, int(p["band_min_cols"]))
    dev = np.max(np.abs(rgb[y0:] - bg[:, None, :]), axis=2)
    cand = np.zeros_like(seed)
    thr_rows = np.broadcast_to(
        np.asarray(thr, float).reshape(-1, 1) if np.ndim(thr) else float(thr), dev.shape
    )
    cand[y0:] = np.nan_to_num(dev, nan=0.0) > thr_rows
    cand[:, :lo] = False
    cand[:, hi + 1 :] = False
    cand &= ~forbid
    lab, n = ndi.label(cand | seed, structure=_EIGHT)
    if n == 0:
        return seed
    keep = np.unique(lab[anchor])
    keep = keep[keep > 0]
    grown = seed | (np.isin(lab, keep) & cand)
    closed = ndi.binary_closing(grown, structure=_EIGHT)
    filled = ndi.binary_fill_holes(closed)
    add = filled & ~grown & ~forbid
    add[:y0] = False
    add[:, :lo] = False
    add[:, hi + 1 :] = False
    added = ndi.binary_opening(
        (grown | add) & ~seed, structure=np.ones((3, 1), bool)
    )  # drop <= 2 px tall haze streaks
    return seed | added


@lru_cache(maxsize=2)
def _palette_lut(palette: tuple, tol: int) -> np.ndarray:
    """Precompute RGB palette matches.

    Args:
        palette: Tuple of RGB triplets.
        tol: Maximum per-channel difference from a palette color.

    Returns:
        Boolean lookup table of shape ``(256, 256, 256)``, indexed by RGB values.
    """
    lut = np.zeros((256, 256, 256), bool)
    for r, g, b in palette:
        lut[
            max(r - tol, 0) : r + tol + 1,
            max(g - tol, 0) : g + tol + 1,
            max(b - tol, 0) : b + tol + 1,
        ] = True
    return lut


def _occluder_mask(rgb_i, dark, p):
    """Find occluder slabs by color, height, and proximity to slab faces.

    Args:
        rgb_i: RGB image with integer channels signed for color subtraction.
        dark: Boolean mask of pixels below the dark luminance threshold.
        p: Segmentation parameters for slab colors and minimum dimensions.

    Returns:
        Boolean mask covering the occluder slabs.
    """
    fc = np.array(p["front_color"])
    front = np.all(np.abs(rgb_i - fc) <= p["front_tol"], axis=2) & dark
    core = _keep_vertical_runs(front, p["min_run"])
    core = _largest_components(core, None, int(p["min_core_area"]))
    lab_c, _ = ndi.label(core, structure=_EIGHT)
    for i, sl in enumerate(ndi.find_objects(lab_c), start=1):
        if sl[0].stop - sl[0].start < int(p["min_core_height"]):
            core[lab_c == i] = False
    occ = core.copy()
    if core.any():
        # slab shade gradient: looser colour match, accepted only where it spans the slab's full height
        ys = np.nonzero(core.any(axis=1))[0]
        height = int(ys.max() - ys.min() + 1)
        ext = np.all(np.abs(rgb_i - fc) <= p["front_tol_ext"], axis=2) & dark
        occ |= _keep_vertical_runs(
            ext, max(int(p["ext_run_frac"] * height), int(p["min_run"]))
        )
        core = occ.copy()
    if p["face_palette"]:
        pal = tuple(tuple(int(v) for v in c) for c in p["face_palette"])
        lut = _palette_lut(pal, int(p["face_tol"]))
        face = (
            lut[
                rgb_i[:, :, 0].clip(0, 255),
                rgb_i[:, :, 1].clip(0, 255),
                rgb_i[:, :, 2].clip(0, 255),
            ]
            & dark
        )
        reach = ndi.binary_dilation(
            core, structure=np.ones((1, 2 * int(p["face_reach"]) + 1), bool)
        )
        occ |= _keep_vertical_runs(face & reach, p["min_run"])
    return occ


def segment_frame(rgb: np.ndarray, params: dict, *, has_occluders=True) -> np.ndarray:
    """Label the background, white object, black object, and occluder.

    Slab color and vertical extent help distinguish the occluder from the black
    object, whose shading can reach the same color range.

    Args:
        rgb: RGB panel with shape ``(height, width, 3)``.
        params: Session thresholds and palettes from ``fit_session_params`` or defaults.
        has_occluders: Whether to identify and exclude occluder slabs.

    Returns:
        A uint8 label image containing BACKGROUND, WHITE, BLACK, or OCCLUDER.
    """
    p = params
    rgb_f = np.asarray(rgb, dtype=float)
    rgb_i = rgb.astype(np.int16)
    lum = luminance(rgb_f)
    dark = lum < p["t_dark"]

    occ = _occluder_mask(rgb_i, dark, p) if has_occluders else np.zeros_like(dark)

    # white object: bright, above the floor strip, <= max_white_components components
    rows = np.arange(lum.shape[0])[:, None]
    white = (
        np.where(rows < p["y_floor"], lum >= p["t_white"], lum >= p["t_white_floor"])
        & ~occ
    )
    white = _largest_components(
        white, int(p["max_white_components"]), int(p["min_area_white"])
    )

    # black object: dark, not occluder; a 3x3 opening removes the 1-2 px dark fringes along
    # occluder/sky boundaries (present on object-free frames); then components >= min area
    black = ndi.binary_opening(dark & ~occ & ~white, structure=_EIGHT)
    black = _largest_components(black, None, int(p["min_area_black"]))

    if p["band_dev_thr"] is not None:
        # floor/glow band: an object's shaded lower rim can be darker than the bright band
        # background, so grow each object into band pixels that stand out from the row background
        span = np.zeros(lum.shape, bool)
        for m in (white, black):
            if m.any():
                cols = np.nonzero(m.any(axis=0))[0]
                span[
                    :,
                    max(cols.min() - int(p["band_excl_margin"]), 0) : cols.max()
                    + int(p["band_excl_margin"])
                    + 1,
                ] = True
        exclude_bg = occ | dark | span
        white_g = _grow_in_band(white, rgb_f, exclude_bg, occ | black | dark, p)
        black_g = _grow_in_band(black, rgb_f, exclude_bg, occ | white_g, p)
        white, black = white_g, black_g & ~white_g

    labels = np.full(lum.shape, BACKGROUND, dtype=np.uint8)
    labels[white] = WHITE
    labels[black] = BLACK
    labels[occ] = OCCLUDER
    return labels


def fit_session_params(
    object_free_frames: Sequence[np.ndarray],
    object_frames: Sequence[np.ndarray],
    *,
    has_occluders: bool = True,
) -> dict:
    """Calibrate segmentation thresholds and colors for one session.

    The dark threshold comes from a valley in the pooled luminance histogram.
    Object-free frames determine the bright thresholds, where the floor band
    starts, and how much floor-band pixels must differ from their background.
    When occluders are present, dark colors in object-free frames also provide
    the slab-face palette.

    Args:
        object_free_frames: Nonempty sequence of RGB panels sampled during ITI.
        object_frames: Sequence of RGB panels sampled during active trials.
        has_occluders: Whether to estimate occluder colors.

    Returns:
        Dictionary of segmentation parameters matching the keys in DEFAULT_PARAMS.
    """
    p = DEFAULT_PARAMS.copy()
    free = np.stack([luminance(f) for f in object_free_frames])
    both = np.concatenate(
        [free.ravel(), *(luminance(f).ravel() for f in object_frames)]
    )
    hist, _ = np.histogram(both, bins=np.arange(36.5, 56.5, 1.0))
    sm = np.convolve(hist, np.ones(3) / 3, mode="same")
    centres = np.arange(37, 56)[: len(hist)]
    window = (centres >= 38) & (centres <= 52)
    flat_min = np.flatnonzero(sm[window] == sm[window].min())
    if hist[window].any():
        p["t_dark"] = float(centres[window][flat_min[len(flat_min) // 2]]) + 0.5
    # object-free frames in which something bright (>= 240, rows < 180: a white object
    # still on screen) appears are left out of the background level
    clean = free[:, : min(180, free.shape[1])].max(axis=(1, 2)) < 240
    if clean.any():
        free = free[clean]
    rowmax = free.max(axis=(0, 2))
    ref_rows = min(180, free.shape[1])
    p["t_white"] = float(1.1 * rowmax[:ref_rows].max())
    over = np.flatnonzero(rowmax >= p["t_white"])
    p["y_floor"] = int(over[0]) if over.size else int(free.shape[1])
    if over.size:
        p["t_white_floor"] = float(1.05 * rowmax[p["y_floor"] :].max())
    # Luminance is at most 255: a higher threshold would silently count no
    # white pixel in the whole session
    for name in ("t_white", "t_white_floor"):
        if p[name] > 255:
            raise ValueError(
                f"{name} {p[name]:.0f} is above 255, so no white object can be "
                "detected: the ITI background is too bright (a stray bright "
                "pixel, or an object still on screen in every sampled ITI frame)"
            )

    # floor-band deviation threshold: 99.5th percentile of |pixel - row background| over the band of
    # the object-free frames (row background = per-row median over non-dark pixels)
    y0 = p["y_floor"]
    bands = [
        np.asarray(f, dtype=float)[y0:]
        for f in object_free_frames
        if y0 < np.asarray(f).shape[0]
    ]
    if bands:
        stack = np.stack(bands)  # (frames, band rows, cols, 3)
        light = (
            luminance(stack.reshape(-1, stack.shape[2], 3)).reshape(stack.shape[:3])
            >= p["t_dark"]
        )
        sampled_rows = light.any(axis=(0, 2))
        thresholds = np.ones(stack.shape[1])
        if sampled_rows.any():
            light = light[:, sampled_rows]
            colors = np.where(light[..., None], stack[:, sampled_rows], np.nan)
            reference = np.nanmedian(colors, axis=(0, 2))
            deviations = np.max(np.abs(colors - reference[None, :, None, :]), axis=3)
            thresholds[sampled_rows] = np.maximum(
                np.nanpercentile(deviations, 99.5, axis=(0, 2)), 1.0
            )
        p["band_dev_thr"] = thresholds.tolist()

    if not has_occluders:
        return p

    cnt: Counter = Counter()
    for f in object_free_frames:
        f = np.asarray(f).astype(np.int64)
        cnt.update(map(tuple, f[luminance(f) < p["t_dark"]].tolist()))
    if cnt:
        modal = cnt.most_common(1)[0][0]
        p["front_color"] = [int(v) for v in modal]
        floor = 5 * len(object_free_frames)
        p["face_palette"] = sorted(
            [int(v) for v in c]
            for c, n in cnt.items()
            if n >= floor and max(abs(c[i] - modal[i]) for i in range(3)) > 3
        )
    return p


def _calibration_frames(frame_ids, episodes, iti):
    """Sample up to 30 trials for segmentation calibration.

    Args:
        frame_ids: Displayed frame ID for each mapped step, in step order.
        episodes: Trial ID for each mapped step.
        iti: Boolean flag for inter-trial interval steps.

    Returns:
        Integer array of shape ``(n_pairs, 2)`` with the penultimate distinct
        pre-trial ITI frame and middle distinct active frame in each pair.
    """
    active = np.flatnonzero(~iti)
    pairs = []
    previous_stop = 0
    for _, group in groupby(active, key=episodes.__getitem__):
        rows = np.fromiter(group, dtype=np.intp)
        before = np.unique(
            frame_ids[previous_stop : rows[0]][iti[previous_stop : rows[0]]]
        )
        before = before[before < frame_ids[rows[0]]]
        during = np.unique(frame_ids[rows])
        if before.size >= 2:
            pairs.append((before[-2], during[len(during) // 2]))
        previous_stop = rows[-1] + 1
    if not pairs:
        return np.empty((0, 2), dtype=np.int64)
    rng = np.random.default_rng(0)
    sample = np.sort(rng.choice(len(pairs), size=min(30, len(pairs)), replace=False))
    return np.asarray(pairs)[sample]


def _silhouette_candidate(labels, mask, count):
    """Measure a mask suitable for fitting an unoccluded silhouette.

    Args:
        labels: Segmentation label image for the panel.
        mask: Boolean mask of the object being measured.
        count: Number of visible pixels in the mask.

    Returns:
        Tuple of log pixel area, x and y centroid, width, and height. Returns
        None for a small mask or one likely to be clipped or occluded.
    """
    if count < 30:
        return None
    ys, xs = np.nonzero(mask)
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
    if x0 < 4 or x1 > mask.shape[1] - 5 or y0 == 0 or y1 == mask.shape[0] - 1:
        return None

    near = ndi.binary_dilation(mask, structure=_EIGHT) & ~mask
    if (near & (labels != BACKGROUND)).any():
        return None
    # Slab boundaries crossing the object's horizontal span also disqualify it.
    covered = (labels[y0 : y1 + 1] == OCCLUDER).mean(axis=0) >= 0.5
    edges = np.flatnonzero(covered[1:] != covered[:-1]) + 0.5
    if ((edges >= x0 - 4) & (edges <= x1 + 4)).any():
        return None
    return np.log(count), xs.mean(), ys.mean(), x1 - x0 + 1, y1 - y0 + 1


def _poly_features(pose, degree):
    """Build a polynomial design matrix.

    Args:
        pose: Array of normalized pose coordinates, one row per observation.
        degree: Maximum total polynomial degree.

    Returns:
        Matrix with an intercept and all monomials through the requested degree.
    """
    columns = [np.ones(len(pose))]
    for order in range(1, degree + 1):
        for axes in combinations_with_replacement(range(pose.shape[1]), order):
            columns.append(np.prod(pose[:, axes], axis=1))
    return np.column_stack(columns)


def _fit_silhouette(pose, observations, episodes):
    """Fit box measurements as functions of pose.

    Args:
        pose: Game x and z coordinates with shape ``(n_frames, 2)``.
        observations: Rows of log area, x and y centroid, width, and height.
            NaN rows indicate masks unsuitable for training.
        episodes: Trial IDs used to keep each trial within a validation fold.

    Returns:
        Fit diagnostics and, when fitted, the degree, pose normalization, and
        coefficients. The degree minimizes held-out log-area error.
    """
    usable = np.isfinite(pose).all(axis=1) & np.isfinite(observations).all(axis=1)
    pose, observations, episodes = pose[usable], observations[usable], episodes[usable]
    rng = np.random.default_rng(0)
    if len(pose) > 2500:
        keep = np.sort(rng.choice(len(pose), size=2500, replace=False))
        pose, observations, episodes = pose[keep], observations[keep], episodes[keep]
    trials, trial_index = np.unique(episodes, return_inverse=True)
    n_folds = min(5, len(trials))
    if n_folds < 2:
        return {"status": "insufficient_trials", "n_frames": len(pose)}

    center = pose.mean(axis=0)
    scale = pose.std(axis=0)
    scale = np.where(scale > 0, scale, 1)
    normalized = (pose - center) / scale
    fold_ids = np.empty(len(trials), dtype=int)
    fold_ids[rng.permutation(len(trials))] = np.arange(len(trials)) % n_folds
    folds = fold_ids[trial_index]

    scores = {}
    for degree in (1, 2, 3):
        design = _poly_features(normalized, degree)
        residuals = np.empty(len(pose))
        for fold in range(n_folds):
            test = folds == fold
            beta, _, rank, _ = np.linalg.lstsq(
                design[~test], observations[~test, 0], rcond=None
            )
            if rank < design.shape[1]:
                break
            residuals[test] = design[test] @ beta - observations[test, 0]
        else:
            scores[degree] = float(np.mean(residuals**2))
    if not scores:
        return {"status": "insufficient_pose_support", "n_frames": len(pose)}

    degree = min(scores, key=scores.get)
    design = _poly_features(normalized, degree)
    coefficients, *_ = np.linalg.lstsq(design, observations, rcond=None)
    return {
        "status": "fitted",
        "n_frames": len(pose),
        "degree": degree,
        "cv_log_area_mse": scores[degree],
        "pose_center": center,
        "pose_scale": scale,
        "coefficients": coefficients,
    }


def _predict_silhouettes(pose, observations, episodes, target_left):
    """Fit and evaluate separate models for left- and right-target trials.

    Args:
        pose: Game x and z coordinates for each active frame.
        observations: Silhouette measurements for one object, with NaN values
            for frames unsuitable for training.
        episodes: Trial ID for each active frame.
        target_left: Target side per frame, with 1 for left, 0 for right, and
            NaN for unknown.

    Returns:
        Tuple of predicted boxes and fit diagnostics keyed by target side. Each
        box is ``(center_x, center_y, width, height)``, with NaN for unavailable fits.
    """
    boxes = np.full((len(pose), 4), np.nan)
    fits = {}
    valid_pose = np.isfinite(pose).all(axis=1)
    for name, value in (("target_left", 1), ("target_right", 0)):
        rows = valid_pose & (target_left == value)
        fit = _fit_silhouette(pose[rows], observations[rows], episodes[rows])
        fits[name] = fit
        if fit["status"] == "fitted":
            normalized = (pose[rows] - fit["pose_center"]) / fit["pose_scale"]
            design = _poly_features(normalized, fit["degree"])
            boxes[rows] = (design @ fit["coefficients"])[:, 1:]
    return boxes, fits


def _surface_cells(mask, box, grid):
    """Project visible pixels into the predicted silhouette grid.

    Args:
        mask: Boolean mask of the visible object.
        box: Predicted ``(center_x, center_y, width, height)`` in pixels.
        grid: Number of cells along each side of the square grid.

    Returns:
        Boolean grid marking cells containing at least one visible pixel.
    """
    cx, cy, width, height = box
    ys, xs = np.nonzero(mask)
    u = np.floor(((xs - cx) / width + 0.5) * grid).astype(int)
    v = np.floor(((ys - cy) / height + 0.5) * grid).astype(int)
    keep = (u >= 0) & (u < grid) & (v >= 0) & (v < grid)
    cells = np.zeros((grid, grid), dtype=bool)
    cells[v[keep], u[keep]] = True
    return cells


def surface_novelty(masks, boxes, episodes, *, grid=SURFACE_GRID):
    """Measure how much of the silhouette is first seen at each active frame.

    Args:
        masks: Iterable of visible object masks in trial and frame order.
        boxes: Predicted ``(center_x, center_y, width, height)`` per mask.
        episodes: Trial ID per mask. Seen cells reset at each trial boundary.
        grid: Number of cells along each side of the square grid.

    Returns:
        Float array of per-frame fractions of the ellipse's cells newly seen.
        Invalid boxes and visible masks outside the predicted ellipse yield NaN.
    """
    centers = (np.arange(grid) + 0.5) / grid - 0.5
    inside = centers[:, None] ** 2 + centers[None, :] ** 2 <= 0.25
    area = np.count_nonzero(inside)
    values = np.full(len(boxes), np.nan)
    seen = np.zeros_like(inside)
    previous_episode = None
    for i, (mask, box, episode) in enumerate(zip(masks, boxes, episodes, strict=True)):
        if episode != previous_episode:
            seen.fill(False)
            previous_episode = episode
        if np.isfinite(box).all() and (box[2:] > 0).all():
            visible = _surface_cells(mask, box, grid) & inside
            if not visible.any() and mask.any():
                continue  # The predicted silhouette missed a visible object.
            values[i] = np.count_nonzero(visible & ~seen) / area
            seen |= visible
    return values


def _read_panels(read_panels, frame_ids):
    """Read and validate the requested RGB panels.

    Args:
        read_panels: Callable accepting sorted frame IDs and yielding RGB panels
            in that order.
        frame_ids: Sorted IDs to request.

    Yields:
        Pairs of frame ID and uint8 RGB panel with shape ``(237, 316, 3)``.
    """
    if not len(frame_ids):
        return
    for frame_id, panel in zip(frame_ids, read_panels(frame_ids), strict=True):
        if panel.shape != (*PANEL_SIZE[::-1], 3) or panel.dtype != np.uint8:
            raise ValueError(f"Unexpected RGB panel shape or type at frame {frame_id}")
        yield frame_id, panel


def _calibrate_session(read_panels, frames, episodes, iti, *, has_occluders):
    """Calibrate segmentation and keep the sampled panels for reuse.

    Args:
        read_panels: Callable yielding RGB panels for sorted frame IDs.
        frames: Displayed frame IDs in step order.
        episodes: Trial ID per mapped step.
        iti: Inter-trial interval flag per mapped step.
        has_occluders: Whether to estimate occluder colors.

    Returns:
        Tuple of segmentation parameters, sampled ITI/active frame pairs, and
        RGB panels keyed by frame ID. Uses defaults if no pairs are available.
    """
    calibration = _calibration_frames(frames, episodes, iti)
    calibration_panels = dict(_read_panels(read_panels, np.unique(calibration)))
    if calibration.size:
        free, objects = calibration.T
        params = fit_session_params(
            [calibration_panels[f] for f in np.unique(free)],
            [calibration_panels[f] for f in np.unique(objects)],
            has_occluders=has_occluders,
        )
    else:
        params = DEFAULT_PARAMS.copy()
    return params, calibration, calibration_panels


def _active_panels(read_panels, frame_ids, calibration_panels):
    """Yield active panels, reusing any decoded for calibration.

    Args:
        read_panels: Callable yielding RGB panels for sorted frame IDs.
        frame_ids: Sorted distinct active frame IDs.
        calibration_panels: Sampled RGB panels keyed by ID.

    Yields:
        One RGB panel per requested frame, in order.
    """
    remaining = frame_ids[~np.isin(frame_ids, list(calibration_panels))]
    with closing(_read_panels(read_panels, remaining)) as panels:
        for frame_id in frame_ids:
            panel = calibration_panels.get(frame_id)
            if panel is None:
                _, panel = next(panels)
            yield panel
        # Exhaust the reader to detect surplus frames.
        next(panels, None)


def _measure_frame(panel, *, labels_to_measure, params, has_occluders):
    """Segment and measure one active frame.

    Args:
        panel: A uint8 RGB panel.
        labels_to_measure: Target and, if present, distractor segmentation labels.
        params: Session segmentation parameters.
        has_occluders: Whether to identify occluder slabs.

    Returns:
        Pixel counts, silhouette training measurements, and packed masks.
        Each sequence follows target, distractor order.
    """
    labels = segment_frame(panel, params, has_occluders=has_occluders)
    counts, observations, masks = [], [], []
    for value in labels_to_measure:
        mask = labels == value
        count = np.count_nonzero(mask)
        counts.append(count)
        observations.append(_silhouette_candidate(labels, mask, count))
        masks.append(zlib.compress(np.packbits(mask), level=1) if count else None)
    return counts, observations, masks


def _measure_frames(panels, measure, frame_workers):
    """Measure panels in order with bounded buffering.

    Args:
        panels: Iterator of RGB panels.
        measure: Picklable callable that measures one panel.
        frame_workers: Number of local workers, or one for serial execution.

    Yields:
        One measurement result per input panel, in order.
    """
    if frame_workers == 1:
        yield from map(measure, panels)
        return

    # Spawn clean workers so they do not inherit the video decoder or DB connection.
    with ProcessPoolExecutor(
        max_workers=frame_workers, mp_context=get_context("spawn")
    ) as pool:
        while batch := list(islice(panels, 8 * frame_workers)):
            yield from pool.map(measure, batch, chunksize=4)


def _segment_frames(
    read_panels,
    frame_ids,
    calibration_panels,
    labels_to_measure,
    params,
    *,
    has_occluders,
    frame_workers,
):
    """Segment each distinct active video frame once.

    Args:
        read_panels: Callable yielding RGB panels for sorted frame IDs.
        frame_ids: Sorted distinct active frame IDs.
        calibration_panels: Sampled RGB panels keyed by ID.
        labels_to_measure: Target and, if present, distractor segmentation labels.
        params: Session segmentation parameters.
        has_occluders: Whether to identify occluder slabs.
        frame_workers: Number of local workers.

    Returns:
        Tuple of per-frame pixel counts, per-frame silhouette training
        measurements, and packed active masks keyed by frame ID. The arrays
        have two object columns in target, distractor order.
    """
    shape = (len(frame_ids), 2)
    counts = np.zeros(shape, dtype=np.int32)
    observations = np.full((*shape, 5), np.nan)
    packed_masks = {}
    if len(frame_ids):
        measure = partial(
            _measure_frame,
            labels_to_measure=labels_to_measure,
            params=params,
            has_occluders=has_occluders,
        )
        with closing(
            _active_panels(read_panels, frame_ids, calibration_panels)
        ) as panels:
            results = _measure_frames(panels, measure, frame_workers)
            with closing(results):
                for i, (frame_id, result) in enumerate(
                    zip(frame_ids, results, strict=True)
                ):
                    frame_counts, candidates, packed_masks[frame_id] = result
                    counts[i, : len(frame_counts)] = frame_counts
                    for obj, candidate in enumerate(candidates):
                        if candidate is not None:
                            observations[i, obj] = candidate
    return counts, observations, packed_masks


def _surface_descriptors(
    frames,
    episodes,
    iti,
    pose,
    target_left,
    by_step,
    observations,
    packed_masks,
    *,
    has_distractor,
    grid,
):
    """Compute trial-level surface novelty and assign it to mapped steps.

    Args:
        frames: Displayed frame IDs in mapped step order.
        episodes: Trial ID per mapped step.
        iti: Inter-trial interval flag per mapped step.
        pose: Game x and z coordinates per mapped step.
        target_left: Target side per mapped step.
        by_step: Index of each mapped step's frame in the distinct-frame arrays.
        observations: Silhouette measurements per distinct frame and object.
        packed_masks: Compressed active-frame object masks keyed by frame ID.
        has_distractor: Whether the task includes a distractor.
        grid: Number of cells along each side of the silhouette grid.

    Returns:
        Tuple of novelty columns in mapped step order and fit diagnostics for
        each object. Shared frames contribute novelty once per trial.
    """
    active = np.flatnonzero(~iti)
    boundaries = (
        np.flatnonzero(
            (np.diff(by_step[active]) != 0) | (np.diff(episodes[active]) != 0)
        )
        + 1
    )
    # Group by trial and frame. Use the last step for pose and credit the first.
    first = active[np.r_[0, boundaries]] if active.size else active
    last = active[np.r_[boundaries - 1, len(active) - 1]] if active.size else active

    descriptors, fit_status = {}, {}
    for obj, name in enumerate(("t_new_surf", "d_new_surf")):
        novelty = np.full(len(frames), np.nan)
        descriptors[name] = novelty
        if obj == 1 and not has_distractor:
            fit_status[name] = {"status": "absent"}
            novelty[active] = 0
            continue

        boxes, fit_status[name] = _predict_silhouettes(
            pose[last],
            observations[by_step[last], obj],
            episodes[last],
            target_left[last],
        )
        if not np.isfinite(boxes).any():
            continue
        masks = (_unpack_mask(packed_masks[frame][obj]) for frame in frames[first])
        increments = surface_novelty(masks, boxes, episodes[first], grid=grid)
        # Shared steps reuse pixel counts, but a frame reveals surface only once.
        novelty[active] = np.repeat(
            np.where(np.isfinite(increments), 0.0, np.nan),
            np.diff(np.r_[0, boundaries, len(active)]),
        )
        novelty[first] = increments
    return descriptors, fit_status


def validate_frame_workers(frame_workers):
    """Check the worker count before processing a session.

    Args:
        frame_workers: Requested number of segmentation processes.

    Returns:
        Positive integer worker count.
    """
    frame_workers = index(frame_workers)
    if frame_workers < 1:
        raise ValueError("frame_workers must be at least one")
    if frame_workers > 1 and current_process().daemon:
        raise ValueError(
            "Use frame_workers=1 in a worker process, or populate with processes=1"
        )
    return frame_workers


def describe_steps(
    read_panels,
    frame_ids,
    episodes,
    iti,
    pose,
    target_left,
    *,
    target_is_white,
    has_distractor,
    has_occluders,
    grid=SURFACE_GRID,
    frame_workers=1,
):
    """Compute visibility descriptors for mapped game steps.

    Args:
        read_panels: Callable accepting sorted distinct frame IDs and yielding
            uint8 RGB panels with shape ``(237, 316, 3)`` in that order.
        frame_ids: One displayed frame ID per game step, with -1 for unmapped
            steps. Mapped IDs must be nondecreasing in step order.
        episodes: Trial ID per game step.
        iti: Boolean inter-trial interval flag per game step.
        pose: Array of game x and z coordinates with shape ``(n_steps, 2)``.
        target_left: Target side per game step, with 1 for left, 0 for right,
            and NaN for unknown.
        target_is_white: Whether the white object is the target.
        has_distractor: Whether the task includes a distractor.
        has_occluders: Whether to segment occluder slabs.
        grid: Number of cells along each side of the silhouette grid.
        frame_workers: Number of CPU workers for independent active frames.
            Use one when the session itself runs inside a worker process.

    Returns:
        Tuple of descriptor columns, calibration metadata, and surface-fit
        diagnostics. Each descriptor row corresponds to a mapped step in
        input order. The columns contain source step index, frame ID, episode,
        object and total pixel counts, visibility state, and per-object novelty.
        Mapped ITI steps have zero counts, state "neither", and NaN novelty.
    """
    frame_workers = validate_frame_workers(frame_workers)
    frame_ids = np.asarray(frame_ids, dtype=np.int64).ravel()
    episodes = np.asarray(episodes).ravel()
    iti = np.asarray(iti, dtype=bool).ravel()
    pose = np.asarray(pose, dtype=float)
    target_left = np.asarray(target_left, dtype=float).ravel()
    if (
        len(episodes) != len(frame_ids)
        or len(iti) != len(frame_ids)
        or len(target_left) != len(frame_ids)
        or pose.shape
        != (
            len(frame_ids),
            2,
        )
    ):
        raise ValueError(
            "Frame mapping, episodes, ITI, game pose, and target side must align by step"
        )
    if (frame_ids < -1).any():
        raise ValueError("Invalid frame ID below -1")

    # Keep the original step indices for joining descriptors back to game state.
    step_index = np.flatnonzero(frame_ids >= 0)
    frames = frame_ids[step_index]
    if (np.diff(frames) < 0).any():
        raise ValueError("Mapped frames must be in chronological order")
    episodes, iti, pose = episodes[step_index], iti[step_index], pose[step_index]
    target_left = target_left[step_index]
    if not np.isfinite(episodes).all():
        raise ValueError("Mapped steps need valid episode IDs")
    # ITI contributes background calibration samples only. A frame shared with
    # an active step is segmented once and its counts are assigned to active steps.
    active = ~iti
    active_frames, active_by_step = np.unique(frames[active], return_inverse=True)
    by_step = np.full(len(frames), -1, dtype=np.intp)
    by_step[active] = active_by_step
    params, calibration, calibration_panels = _calibrate_session(
        read_panels, frames, episodes, iti, has_occluders=has_occluders
    )

    target, distractor = (WHITE, BLACK) if target_is_white else (BLACK, WHITE)
    labels_to_measure = (target, distractor) if has_distractor else (target,)
    counts, observations, packed_masks = _segment_frames(
        read_panels,
        active_frames,
        calibration_panels,
        labels_to_measure,
        params,
        has_occluders=has_occluders,
        frame_workers=frame_workers,
    )

    # Keep ITI steps in the output timeline with known zero counts.
    step_counts = np.zeros((len(frames), 2), dtype=counts.dtype)
    step_counts[active] = counts[active_by_step]
    t_px, d_px = step_counts.T
    states = np.asarray(["neither", "target_only", "distractor_only", "both"])
    descriptors = {
        "step_index": step_index,
        "frame_id": frames,
        "episode": episodes,
        "t_px": t_px,
        "d_px": d_px,
        "total_visible_px": t_px + d_px,
        "visibility_state": states[(t_px > 0).astype(int) + 2 * (d_px > 0)],
    }
    surface, fit_status = _surface_descriptors(
        frames,
        episodes,
        iti,
        pose,
        target_left,
        by_step,
        observations,
        packed_masks,
        has_distractor=has_distractor,
        grid=grid,
    )
    descriptors.update(surface)

    calibration_info = {
        "parameters": params,
        "frame_pairs": calibration,
        "status": "fitted" if calibration.size else "defaults",
        "panel_size": PANEL_SIZE,
        "surface_grid": grid,
    }
    return descriptors, calibration_info, fit_status


def _unpack_mask(data):
    """Restore an active-frame object mask.

    Args:
        data: Compressed packed bits from segmentation, or None for an empty mask.

    Returns:
        Mask with the native analysis panel shape ``(237, 316)``.
    """
    shape = PANEL_SIZE[::-1]
    if data is None:
        return np.zeros(shape, dtype=bool)
    packed = np.frombuffer(zlib.decompress(data), dtype=np.uint8)
    return np.unpackbits(packed, count=shape[0] * shape[1]).reshape(shape)

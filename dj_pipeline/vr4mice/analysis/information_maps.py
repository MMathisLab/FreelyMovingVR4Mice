"""Information maps: how much of each target is visible from each arena position.

For a given occluder aperture, the map stores, for every (x, y) position of a
viewer at a fixed height, the visible area of the left and right target
circles (each scaled by distance), combined with ``info_metric``.

Apertures are given in game units (``game_aperture``) and converted to the
info-map geometry's arena units (``infomap_aperture``) with
``convert_game_to_infomap_aperture``, using the calibrated occlusion levels in
``APERTURE_CALIBRATION``. Their percent of target visible is stored in
``information_maps.OcclusionAperture``.
"""

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm

# Calibrated occlusion levels as (game_aperture, infomap_aperture) pairs,
# sorted by aperture: 0, 10, 35, 72 and 99 percent of target visible.
APERTURE_CALIBRATION = [
    (3.0, 8.7),
    (4.2, 12.3),
    (6.0, 17.3),
    (8.48, 24.5),
    (12.0, 34.6),
]


@dataclass
class Arena:
    length: float
    width: float
    height: float


# Rig arena geometry, in info-map arena units.
ARENA = Arena(length=52.0, width=52.0, height=50.0)

# Rig positions (cm, as in the trajectories) covered by the map: both x and y
# span [-POSITION_OFFSET, POSITION_SPAN - POSITION_OFFSET].
POSITION_OFFSET = 27.0
POSITION_SPAN = 54.0


class Aperture:
    def __init__(self, arena: Arena, opening_width: float):
        validate_opening_width(opening_width, arena.width)

        gap_width = opening_width / 2.0
        self.height = arena.height
        self.width = arena.width / 2.0 - gap_width
        self.gap_width = gap_width
        self.wall_depth = arena.length - 10
        self.left_wall_edge = (self.width, self.wall_depth)
        self.right_wall_edge = (arena.width / 2.0 + gap_width, self.wall_depth)
        self.left_wall = (0, self.wall_depth)
        self.right_wall = (arena.width / 2.0 + gap_width, self.wall_depth)


def validate_opening_width(opening_width: float, arena_width: float) -> None:
    if opening_width < 0:
        raise ValueError(f"Aperture width must be >= 0; got {opening_width}.")
    if opening_width >= arena_width:
        raise ValueError(
            f"Aperture width must be smaller than arena width ({arena_width}); "
            f"got {opening_width}."
        )


def convert_game_to_infomap_aperture(game_aperture):
    """Convert game-unit aperture to info-map aperture using calibration pairs.

    Uses linear interpolation between the ``APERTURE_CALIBRATION`` points and
    linear extrapolation outside the calibrated range.
    """
    game_points, infomap_points = np.array(APERTURE_CALIBRATION, dtype=float).T

    if game_aperture < game_points[0]:
        slope = (infomap_points[1] - infomap_points[0]) / (
            game_points[1] - game_points[0]
        )
        return float(infomap_points[0] + slope * (game_aperture - game_points[0]))

    if game_aperture > game_points[-1]:
        slope = (infomap_points[-1] - infomap_points[-2]) / (
            game_points[-1] - game_points[-2]
        )
        return float(infomap_points[-1] + slope * (game_aperture - game_points[-1]))

    return float(np.interp(game_aperture, game_points, infomap_points))


def target_circle_centers(arena: Arena, separation: float = 23.0):
    """Position target circles at a fixed separation, centered in the arena."""
    circle_l = (
        arena.width / 2.0 - separation / 2.0,
        arena.width,
        arena.height / 2.0,
    )
    circle_r = (
        arena.width / 2.0 + separation / 2.0,
        arena.width,
        arena.height / 2.0,
    )
    return circle_l, circle_r


def _prepare_circle_cache(circle_center, radius, angle_step_degrees, aperture):
    d_theta = np.deg2rad(angle_step_degrees)
    angles = np.arange(0, 2 * np.pi, d_theta)
    if angles.size:
        angles = angles[:-1]

    target_x = circle_center[0] + radius * np.cos(angles)
    target_z = circle_center[2] + radius * np.sin(angles)
    target_y = np.full_like(target_x, circle_center[1], dtype=float)

    left_x = aperture.left_wall_edge[0] - target_x
    left_y = aperture.left_wall_edge[1] - target_y
    right_x = aperture.right_wall_edge[0] - target_x
    right_y = aperture.right_wall_edge[1] - target_y

    left_norm = np.sqrt(left_x * left_x + left_y * left_y)
    right_norm = np.sqrt(right_x * right_x + right_y * right_y)

    left_x_unit = np.zeros_like(left_x)
    left_y_unit = np.zeros_like(left_y)
    right_x_unit = np.zeros_like(right_x)
    right_y_unit = np.zeros_like(right_y)

    np.divide(left_x, left_norm, out=left_x_unit, where=left_norm > 0)
    np.divide(left_y, left_norm, out=left_y_unit, where=left_norm > 0)
    np.divide(right_x, right_norm, out=right_x_unit, where=right_norm > 0)
    np.divide(right_y, right_norm, out=right_y_unit, where=right_norm > 0)

    wall_valid = (left_norm > 0) & (right_norm > 0)
    return (
        angles,
        target_x,
        target_y,
        target_z,
        left_x_unit,
        left_y_unit,
        right_x_unit,
        right_y_unit,
        wall_valid,
    )


def _visible_angles_from_cache(source, cache):
    (
        angles,
        target_x,
        target_y,
        target_z,
        left_x_unit,
        left_y_unit,
        right_x_unit,
        right_y_unit,
        wall_valid,
    ) = cache

    source_x = source[0] - target_x
    source_y = source[1] - target_y
    source_z = source[2] - target_z

    source_norm = np.sqrt(
        source_x * source_x + source_y * source_y + source_z * source_z
    )
    source_x_unit = np.zeros_like(source_x)
    source_y_unit = np.zeros_like(source_y)
    np.divide(source_x, source_norm, out=source_x_unit, where=source_norm > 0)
    np.divide(source_y, source_norm, out=source_y_unit, where=source_norm > 0)

    cross_ls = left_x_unit * source_y_unit - left_y_unit * source_x_unit
    cross_rs = source_x_unit * right_y_unit - source_y_unit * right_x_unit
    visible = wall_valid & (source_norm > 0) & (cross_ls >= 0) & (cross_rs >= 0)
    return angles[visible]


def _get_segment_area_sorted(angles, radius):
    if angles.size == 0:
        return np.array([0.0, 0.0], dtype=float)
    if 0 in angles:
        diffs = np.diff(angles, append=angles[-1] - angles[0])
    else:
        diffs = np.abs(np.diff(angles, append=angles[0]))
    central_angle = np.max([np.max(diffs), np.min(diffs)])
    area = 0.5 * radius**2 * (central_angle - np.sin(central_angle))
    area_c = np.abs(np.pi * radius**2 - area)
    return np.array([area, area_c])


def info_metric(area1, area2):
    return 0.5 * np.abs(area1 + area2)


def _info_map_grid(
    arena,
    circle1_center,
    circle2_center,
    aperture,
    radius,
    x_resolution=150,
    y_resolution=150,
    source_height=20,
    angle_step_degrees=1.0,
    show_progress=True,
):
    x = np.linspace(0, arena.length, x_resolution)
    y = np.linspace(0, aperture.wall_depth, y_resolution)

    info_map = np.zeros((x_resolution, y_resolution))
    cache_l = _prepare_circle_cache(
        circle1_center, radius, angle_step_degrees, aperture
    )
    cache_r = _prepare_circle_cache(
        circle2_center, radius, angle_step_degrees, aperture
    )

    left_dist = np.sqrt(
        (x[:, None] - circle1_center[0]) ** 2
        + (y[None, :] - circle1_center[1]) ** 2
        + (source_height - circle1_center[2]) ** 2
    )
    right_dist = np.sqrt(
        (x[:, None] - circle2_center[0]) ** 2
        + (y[None, :] - circle2_center[1]) ** 2
        + (source_height - circle2_center[2]) ** 2
    )

    iterator = tqdm(range(x_resolution), disable=not show_progress)
    for i in iterator:
        for j in range(y_resolution):
            source = (x[i], y[j], source_height)
            visible_angles_l = _visible_angles_from_cache(source, cache_l)
            visible_angles_r = _visible_angles_from_cache(source, cache_r)

            area_circle1 = _get_segment_area_sorted(visible_angles_l, radius)
            area_circle2 = _get_segment_area_sorted(visible_angles_r, radius)

            # Legacy logic: choose segment type per side by visible arc size.
            if visible_angles_l.size > 180:
                a1 = np.max(area_circle1)
            else:
                a1 = np.min(area_circle1)
            if visible_angles_r.size > 180:
                a2 = np.max(area_circle2)
            else:
                a2 = np.min(area_circle2)

            info_map[i, j] = info_metric(a1 / left_dist[i, j], a2 / right_dist[i, j])
    return info_map


def compute_info_map(
    infomap_aperture,
    arena,
    radius=5.8,
    target_separation=23.0,
    x_resolution=52,
    y_resolution=None,
    source_height=31.0,
    angle_step_degrees=1.0,
    show_progress=True,
):
    """Compute the unnormalized info map for one aperture width (arena units).

    Args:
        infomap_aperture: aperture opening width in info-map arena units
            (convert a game aperture with ``convert_game_to_infomap_aperture``).
        arena: arena geometry.
        radius: target circle radius.
        target_separation: distance between left and right target centers.
        x_resolution: number of lateral rows.
        y_resolution: number of depth columns. Defaults to
            ``arena.length - 10`` (aperture plane as final column).
        source_height: height of the viewer.
        angle_step_degrees: angular sampling step of the target outline.
        show_progress: show a tqdm progress bar.

    Returns:
        Array of shape (x_resolution, y_resolution).
    """
    if y_resolution is None:
        y_resolution = int(round(arena.length - 10))
    if y_resolution <= 0:
        raise ValueError(f"y_resolution must be > 0; got {y_resolution}.")

    validate_opening_width(infomap_aperture, arena.width)
    if np.isclose(infomap_aperture, 0.0):
        return np.zeros((x_resolution, y_resolution))

    aperture = Aperture(arena=arena, opening_width=infomap_aperture)
    circle_l, circle_r = target_circle_centers(arena, separation=target_separation)
    return _info_map_grid(
        arena=arena,
        circle1_center=circle_l,
        circle2_center=circle_r,
        aperture=aperture,
        radius=radius,
        x_resolution=x_resolution,
        y_resolution=y_resolution,
        source_height=source_height,
        angle_step_degrees=angle_step_degrees,
        show_progress=show_progress,
    )


def info_at_position(
    info_map,
    x,
    y,
    normalize_by=None,
    position_offset=POSITION_OFFSET,
    position_span=POSITION_SPAN,
):
    """Info value at rig position(s) (x, y), in the same units as the trajectories.

    Positions are shifted by ``position_offset`` and scaled from
    ``position_span`` to the map resolution, as in the Figure 4 notebook's
    ``get_info_at_position``. Works on scalars or arrays; NaN positions give
    NaN and positions outside the map are clipped to its edge.

    Args:
        info_map: info map of shape (x_resolution, y_resolution), as stored
            in ``InformationMap`` (not rotated).
        x: lateral position(s).
        y: depth position(s).
        normalize_by: if given, divide info values by it (e.g. the max across
            the maps being compared, see ``InformationMap.max_info``).
        position_offset: offset added to positions so they start at 0.
        position_span: range of positions covered by the map.

    Returns:
        Info value(s), same shape as ``x``.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n_x, n_y = info_map.shape
    out = np.full(np.broadcast(x, y).shape, np.nan)
    x, y = np.broadcast_arrays(x, y)
    valid = np.isfinite(x) & np.isfinite(y)

    x_idx = (np.trunc(x[valid] + position_offset) * (n_x - 1) / position_span).astype(
        int
    )
    y_idx = (np.trunc(y[valid] + position_offset) * (n_y - 1) / position_span).astype(
        int
    )
    out[valid] = info_map[np.clip(x_idx, 0, n_x - 1), np.clip(y_idx, 0, n_y - 1)]
    if normalize_by is not None:
        out = out / normalize_by
    return out if out.ndim else float(out)


def info_map_filename(infomap_aperture, prefix="info_matrix_unnormalized"):
    """Filename stem used for saved maps, e.g. ``info_matrix_unnormalized_12.3w``."""
    return f"{prefix}_{infomap_aperture:g}w"


def aperture_label(infomap_aperture, game_aperture=None, visible_percent=None):
    """One-line description of an aperture using the InformationMap field names."""
    parts = []
    if game_aperture is not None:
        parts.append(f"game_aperture={float(game_aperture):g}")
    if visible_percent is not None and visible_percent == visible_percent:
        parts.append(f"visible_percent={int(visible_percent)}%")
    parts.append(f"infomap_aperture={infomap_aperture:g}")
    return " | ".join(parts)


def plot_info_map(
    info_map,
    infomap_aperture,
    game_aperture=None,
    visible_percent=None,
    ax=None,
    normalize_by=None,
    rig_coordinates=False,
    title=True,
    colorbar=True,
    **imshow_kwargs,
):
    """Heatmap of an info map; returns the matplotlib figure.

    Args:
        info_map: info map of shape (x_resolution, y_resolution).
        infomap_aperture: aperture width in info-map arena units (for the title).
        game_aperture: aperture width in game units (for the title).
        visible_percent: percent of target visible (for the title).
        ax: axes to draw on, e.g. to use the map as a trajectory background.
            A new figure is created if None.
        normalize_by: if given, divide the map by it (e.g. the max across the
            maps being compared, see ``InformationMap.max_info``).
        rig_coordinates: draw in rig positions (cm, x lateral / y depth, same
            as the trajectories and ``info_at_position``) instead of map indices.
        title: add a title with the aperture and value range.
        colorbar: add a colorbar.
        **imshow_kwargs: passed to ``ax.imshow`` (e.g. ``cmap``, ``zorder``).
    """
    if normalize_by is not None:
        info_map = info_map / normalize_by
    new_figure = ax is None
    if new_figure:
        fig, ax = plt.subplots(figsize=(6, 5))
    else:
        fig = ax.figure

    imshow_kwargs = {"cmap": "cividis", **imshow_kwargs}
    if rig_coordinates:
        low = -POSITION_OFFSET
        high = POSITION_SPAN - POSITION_OFFSET
        # Transposed so rows are depth (y) and columns lateral (x).
        image = ax.imshow(
            info_map.T, origin="lower", extent=[low, high, low, high], **imshow_kwargs
        )
        ax.set_xlabel("x position (cm)")
        ax.set_ylabel("y position (cm)")
    else:
        image = ax.imshow(info_map, origin="lower", aspect="auto", **imshow_kwargs)
        ax.set_xlabel("Y index")
        ax.set_ylabel("X index")

    if title:
        ax.set_title(
            f"{'Normalized' if normalize_by is not None else 'Unnormalized'} Info Map\n"
            f"{aperture_label(infomap_aperture, game_aperture, visible_percent)}\n"
            f"min={info_map.min():.3f}, max={info_map.max():.3f}"
        )
    if colorbar:
        fig.colorbar(image, ax=ax, label="Information")
    if new_figure:
        fig.tight_layout()
    return fig


def save_info_map_plot(
    info_map,
    output_path: Path,
    infomap_aperture,
    game_aperture=None,
    visible_percent=None,
):
    fig = plot_info_map(info_map, infomap_aperture, game_aperture, visible_percent)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)

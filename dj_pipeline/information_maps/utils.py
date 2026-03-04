import numpy as np
from tqdm import tqdm


def _normalize(vector):
    norm = np.linalg.norm(vector)
    if norm == 0:
        return None
    return vector / norm


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


def get_visibility(source, target, aperture):
    v_t2Lwall = np.subtract(aperture.left_wall_edge + (target[2],), target)
    v_t2Lwall = _normalize(v_t2Lwall)
    v_t2Rwall = np.subtract(aperture.right_wall_edge + (target[2],), target)
    v_t2Rwall = _normalize(v_t2Rwall)

    v_t2s = np.subtract(source, target)
    v_t2s = _normalize(v_t2s)
    if v_t2s is None or v_t2Lwall is None or v_t2Rwall is None:
        return False
    cross_LS = np.cross(v_t2Lwall[:2], v_t2s[:2])
    cross_RS = np.cross(
        v_t2s[:2],
        v_t2Rwall[:2],
    )

    if cross_LS >= 0 and cross_RS >= 0:
        return True
    else:
        return False


def get_visible_angles(source, circle_center, radius, aperture, angle_step_degrees=1.0):
    cache = _prepare_circle_cache(circle_center, radius, angle_step_degrees, aperture)
    return _visible_angles_from_cache(source, cache)


def get_segment_area(angles, radius):
    angles = np.asarray(angles, dtype=float)
    if angles.size == 0:
        return (0, 0)
    return _get_segment_area_sorted(np.sort(angles), radius)


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


def infoMetric(area1, area2):
    return 0.5 * np.abs(area1 + area2)


def info_map(
    arena,
    circle1_center,
    circle2_center,
    aperture,
    radius,
    x_resolution=150,
    y_resolution=150,
    source_height=20,
    angle_step_degrees=1.0,
):

    x = np.linspace(0, arena.length, x_resolution)
    y = np.linspace(0, aperture.wall_depth, y_resolution)

    info_mat = np.zeros((x_resolution, y_resolution))
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
    left_scale = left_dist
    right_scale = right_dist

    iterator = tqdm(range(x_resolution))
    for i in iterator:
        for j in range(y_resolution):
            source = (x[i], y[j], source_height)
            visible_anglesL = _visible_angles_from_cache(source, cache_l)
            visible_anglesR = _visible_angles_from_cache(source, cache_r)

            area_circle1 = _get_segment_area_sorted(visible_anglesL, radius)
            area_circle2 = _get_segment_area_sorted(visible_anglesR, radius)

            # Legacy logic: choose segment type per side by visible arc size.
            if visible_anglesL.size > 180:
                A1 = np.max(area_circle1)
            else:
                A1 = np.min(area_circle1)
            if visible_anglesR.size > 180:
                A2 = np.max(area_circle2)
            else:
                A2 = np.min(area_circle2)

            info_mat[i, j] = infoMetric(A1 / left_scale[i, j], A2 / right_scale[i, j])
    return info_mat

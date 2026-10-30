"""Unit tests for information_maps.py (geometry, calibration, map computation)."""

from pathlib import Path

import numpy as np
import pytest

from information_maps import (
    APERTURE_CALIBRATION,
    Arena,
    compute_info_map,
    convert_game_to_infomap_aperture,
    info_map_filename,
)

REFERENCE_DIR = (
    Path(__file__).parent.parent.parent
    / "dj_pipeline"
    / "information_maps"
    / "info_maps"
)
ARENA = Arena(length=52.0, width=52.0, height=50.0)


def test_calibration_points_map_exactly():
    """Calibrated game apertures convert to their paired info-map aperture."""
    for game_aperture, infomap_aperture in APERTURE_CALIBRATION:
        assert convert_game_to_infomap_aperture(game_aperture) == pytest.approx(
            infomap_aperture
        )


def test_conversion_extrapolates_outside_calibration():
    """Game apertures outside the calibrated range are linearly extrapolated."""
    assert convert_game_to_infomap_aperture(15.0) > 34.6
    assert convert_game_to_infomap_aperture(2.0) < 8.7


def test_zero_aperture_gives_empty_map():
    info_map = compute_info_map(0.0, ARENA, show_progress=False)
    assert info_map.shape == (52, 42)
    assert not info_map.any()


def test_aperture_wider_than_arena_raises():
    with pytest.raises(ValueError):
        compute_info_map(52.0, ARENA, show_progress=False)


@pytest.mark.parametrize("game_aperture", [4.2, 12.0])
def test_matches_reference_maps(game_aperture):
    """Default parameters reproduce the committed reference info maps."""
    infomap_aperture = convert_game_to_infomap_aperture(game_aperture)
    reference = np.load(REFERENCE_DIR / f"{info_map_filename(infomap_aperture)}.npy")

    info_map = compute_info_map(infomap_aperture, ARENA, show_progress=False)

    np.testing.assert_allclose(info_map, reference)


def test_plot_info_map_returns_figure():
    import matplotlib

    matplotlib.use("Agg")
    from information_maps import plot_info_map

    fig = plot_info_map(
        np.ones((52, 42)), infomap_aperture=12.3, game_aperture=4.2, visible_percent=10
    )
    assert fig.axes


def _notebook_get_info_at_position(info_matrix, position):
    """Copy of get_info_at_position from Paper_figures/Figure_4.ipynb."""
    x, y = position
    x_idx = int(x + 27)
    y_idx = int(y + 27)
    x_idx_norm = int(x_idx * (51 / 54))
    y_idx_norm = int(y_idx * (41 / 54))
    y_idx_norm = info_matrix.shape[0] - 1 - y_idx_norm
    return info_matrix[y_idx_norm, x_idx_norm]


def test_info_at_position_matches_notebook():
    """Lookup on the stored map equals the notebook lookup on the rotated map."""
    from information_maps import info_at_position

    rng = np.random.default_rng(0)
    info_map = rng.random((52, 42))
    x = rng.uniform(-27, 27, 500)
    y = rng.uniform(-27, 27, 500)

    expected = [
        _notebook_get_info_at_position(np.rot90(info_map, k=1), (xi, yi))
        for xi, yi in zip(x, y)
    ]

    np.testing.assert_array_equal(info_at_position(info_map, x, y), expected)
    assert info_at_position(info_map, x[0], y[0]) == expected[0]


def test_info_at_position_nan_and_out_of_range():
    from information_maps import info_at_position

    info_map = np.arange(52 * 42, dtype=float).reshape(52, 42)
    values = info_at_position(info_map, [np.nan, 100.0], [0.0, 100.0])
    assert np.isnan(values[0])
    assert values[1] == info_map[-1, -1]


def test_aperture_label_uses_field_names():
    from decimal import Decimal

    from information_maps import aperture_label

    assert (
        aperture_label(12.3, Decimal("4.20"), 10)
        == "game_aperture=4.2 | visible_percent=10% | infomap_aperture=12.3"
    )
    assert aperture_label(43.208, 15.0, None) == (
        "game_aperture=15 | infomap_aperture=43.208"
    )
    assert aperture_label(11.7, 4.0, float("nan")) == (
        "game_aperture=4 | infomap_aperture=11.7"
    )


def test_info_at_position_normalize_by():
    from information_maps import info_at_position

    info_map = np.arange(52 * 42, dtype=float).reshape(52, 42)
    x = np.array([-10.0, 0.0, 20.0])
    y = np.array([5.0, -3.0, 10.0])
    np.testing.assert_allclose(
        info_at_position(info_map, x, y, normalize_by=4.0),
        info_at_position(info_map, x, y) / 4.0,
    )


def test_plot_rig_coordinates_matches_notebook_background():
    """Rig-coordinate plot renders like the notebook's rot90 + imshow background."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from information_maps import plot_info_map

    info_map = np.random.default_rng(1).random((52, 42))
    max_value = 2.0

    def render(draw):
        fig, ax = plt.subplots(figsize=(4, 4))
        draw(ax)
        ax.set_xlim(-27, 27)
        ax.set_ylim(-27, 27)
        ax.set_axis_off()
        fig.canvas.draw()
        pixels = np.asarray(fig.canvas.buffer_rgba()).copy()
        plt.close(fig)
        return pixels

    notebook = render(
        lambda ax: ax.imshow(
            np.rot90(info_map / max_value, k=1),
            cmap="bone",
            extent=[-27, 27, -27, 27],
            zorder=-10,
        )
    )
    table = render(
        lambda ax: plot_info_map(
            info_map,
            12.3,
            ax=ax,
            normalize_by=max_value,
            rig_coordinates=True,
            title=False,
            colorbar=False,
            cmap="bone",
            zorder=-10,
        )
    )
    np.testing.assert_array_equal(table, notebook)

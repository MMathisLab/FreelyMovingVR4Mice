#!/usr/bin/env python3
"""Generate unnormalized information maps for calibrated occlusion shapes.

Occlusion/visibility correspondence used for downstream analyses:

- Visibility buckets (percent object visible): 0, 10, 35, 72, 99.
- In-game aperture widths (legacy game units) mapped to visibility:
    {3.0: 0, 4.2: 10, 6.0: 35, 8.48: 72, 12.0: 99}
- Aperture widths used by this info-map generator (arena units) mapped to
    the same visibility buckets:
    {8.7: 0, 12.3: 10, 17.3: 35, 24.5: 72, 34.6: 99}

The two aperture scales are not numerically identical, but they represent the
same ordered occlusion conditions.

Additional optional set:
- "extra_8_15": game apertures 8 and 15 (game units), converted to this
    script's arena-unit aperture scale using the paired calibration points above.
- "new_15_4_7p75_5p57_10p78_8": game apertures
    [15, 4, 7.75, 5.57, 10.78, 8, 5],
    converted to this script's arena-unit aperture scale.

You can also provide a custom array of game-unit apertures directly with
`--game-aperture-widths` (for example: 15 4 7.75 5.57 10.78).
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from utils import info_map


GAME_APERTURE_TO_VISIBLE_PERCENT = {
        3.0: 0,
        4.2: 10,
        6.0: 35,
        8.48: 72,
        12.0: 99,
}

INFOMAP_APERTURE_TO_VISIBLE_PERCENT = {
        8.7: 0,
        12.3: 10,
        17.3: 35,
        24.5: 72,
        34.6: 99,
}

OCCLUSION_SHAPE_SETS = {
    "base_calibration": [3.0, 4.2, 6.0, 8.48, 12.0],
    "shape_calibration": [15.0, 4.0, 7.75, 5.57, 10.78, 8.0, 5.0],
}


@dataclass
class Arena:
    length: float
    width: float
    height: float


class Aperture:
    def __init__(self, arena: Arena, opening_width: float):
        if opening_width < 0:
            raise ValueError("Aperture width must be >= 0.")
        if opening_width >= arena.width:
            raise ValueError("Aperture width must be smaller than arena width.")

        gap_width = opening_width / 2.0
        self.height = arena.height
        self.width = arena.width / 2.0 - gap_width
        self.gap_width = gap_width
        self.wall_depth = arena.length - 10
        self.left_wall_edge = (self.width, self.wall_depth)
        self.right_wall_edge = (arena.width / 2.0 + gap_width, self.wall_depth)
        self.left_wall = (0, self.wall_depth)
        self.right_wall = (arena.width / 2.0 + gap_width, self.wall_depth)


def parse_args():
    """Parse CLI arguments for info-map generation.

    Note:
        `--aperture-widths` should be provided in this script's arena-unit
        scale. For standard occlusion shapes, use:
        - 8.7 (0% visible)
        - 12.3 (10% visible)
        - 17.3 (35% visible)
        - 24.5 (72% visible)
        - 34.6 (99% visible)

        These correspond to in-game occlusion levels represented by aperture
        widths 3.0, 4.2, 6.0, 8.48, and 12.0 respectively.
    """
    default_out_dir = Path.cwd() / "data"
    parser = argparse.ArgumentParser(
        description=(
            "Generate unnormalized information maps for one or more aperture widths."
        )
    )
    parser.add_argument(
        "--aperture-widths",
        type=float,
        nargs="+",
        default=None,
        help=(
            "Aperture opening widths in arena units. If omitted, use "
            "--occlusion-shape-set to generate widths from visibility buckets."
        ),
    )
    parser.add_argument(
        "--occlusion-shape-set",
        choices=sorted(OCCLUSION_SHAPE_SETS.keys()),
        default=None,
        help=(
            "Named game-aperture set to generate from calibration. "
            "Examples: 'base_calibration', 'extra_8_15', "
            "'new_15_4_7p75_5p57_10p78_8'."
        ),
    )
    parser.add_argument(
        "--game-aperture-widths",
        type=float,
        nargs="+",
        default=None,
        help=(
            "Aperture widths in game units; values are converted to this "
            "script's arena-unit scale using calibration correspondences."
        ),
    )
    parser.add_argument("--arena-length", type=float, default=52.0)
    parser.add_argument("--arena-width", type=float, default=52.0)
    parser.add_argument("--arena-height", type=float, default=50.0)
    parser.add_argument(
        "--radius", type=float, default=5.8, help="Target circle radius."
    )
    parser.add_argument("--x-resolution", type=int, default=52)
    parser.add_argument(
        "--y-resolution",
        type=int,
        default=None,
        help=(
            "Number of depth columns. Defaults to arena_length - 10 "
            "(aperture plane as final column)."
        ),
    )
    parser.add_argument("--source-height", type=float, default=31.0)
    parser.add_argument(
        "--angle-step-degrees",
        type=float,
        default=1.0,
        help="Angular sampling step used to estimate visible segment area.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=default_out_dir,
        help=f"Output directory for .npy files (default: {default_out_dir}).",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="info_matrix_unnormalized",
        help="Output filename prefix.",
    )

    parser.add_argument(
        "--plot",
        action="store_true",
        help="Save a heatmap PNG next to each generated .npy info map.",
    )
    args = parser.parse_args()

    selected_modes = [
        args.aperture_widths is not None,
        args.occlusion_shape_set is not None,
        args.game_aperture_widths is not None,
    ]
    if sum(selected_modes) == 0:
        parser.error(
            "provide one of: --aperture-widths, --game-aperture-widths, "
            "or --occlusion-shape-set."
        )
    if sum(selected_modes) > 1:
        parser.error(
            "use only one input mode: --aperture-widths, "
            "--game-aperture-widths, or --occlusion-shape-set."
        )

    return args


def _visible_to_aperture_map(aperture_to_visible):
    """Invert {aperture: visible} into sorted (visible, aperture) arrays."""
    visible_to_aperture = {visible: aperture for aperture, visible in aperture_to_visible.items()}
    visible_levels = np.array(sorted(visible_to_aperture.keys()), dtype=float)
    aperture_levels = np.array(
        [visible_to_aperture[level] for level in visible_levels], dtype=float
    )
    return visible_levels, aperture_levels


def _calibration_game_to_infomap_pairs():
    """Return aligned game/info-map aperture arrays from shared visibility keys."""
    game_visible_to_aperture = {
        visible: aperture for aperture, visible in GAME_APERTURE_TO_VISIBLE_PERCENT.items()
    }
    infomap_visible_to_aperture = {
        visible: aperture
        for aperture, visible in INFOMAP_APERTURE_TO_VISIBLE_PERCENT.items()
    }
    shared_visible = sorted(
        set(game_visible_to_aperture.keys()) & set(infomap_visible_to_aperture.keys())
    )
    if len(shared_visible) < 2:
        raise ValueError("Need at least two shared calibration points.")

    game_apertures = np.array(
        [game_visible_to_aperture[v] for v in shared_visible], dtype=float
    )
    infomap_apertures = np.array(
        [infomap_visible_to_aperture[v] for v in shared_visible], dtype=float
    )
    return game_apertures, infomap_apertures


def convert_game_to_infomap_aperture(game_aperture):
    """Convert game-unit aperture to info-map aperture using calibration pairs.

    Uses linear interpolation between known calibration points and linear
    extrapolation outside the calibrated range.
    """
    game_points, infomap_points = _calibration_game_to_infomap_pairs()

    if game_aperture < game_points[0]:
        slope = (infomap_points[1] - infomap_points[0]) / (game_points[1] - game_points[0])
        return float(infomap_points[0] + slope * (game_aperture - game_points[0]))

    if game_aperture > game_points[-1]:
        slope = (infomap_points[-1] - infomap_points[-2]) / (
            game_points[-1] - game_points[-2]
        )
        return float(infomap_points[-1] + slope * (game_aperture - game_points[-1]))

    return float(np.interp(game_aperture, game_points, infomap_points))


def apertures_from_game_set(game_apertures):
    """Build game/infomap aperture pairs for requested game apertures."""
    mapping = []
    for game_aperture in game_apertures:
        mapping.append(
            {
                "game_aperture": float(game_aperture),
                "infomap_aperture": convert_game_to_infomap_aperture(game_aperture),
            }
        )
    return mapping


def validate_opening_width(opening_width: float, arena_width: float) -> None:
    if opening_width < 0:
        raise ValueError(f"Aperture width must be >= 0; got {opening_width}.")
    if opening_width >= arena_width:
        raise ValueError(
            f"Aperture width must be smaller than arena width ({arena_width}); "
            f"got {opening_width}."
        )


def target_circle_centers(arena: Arena):
    """Position target circles at fixed separation of 23 units."""
    fixed_separation = 23.0
    circle_l = (
        arena.width / 2.0 - fixed_separation / 2.0,
        arena.width,
        arena.height / 2.0,
    )
    circle_r = (
        arena.width / 2.0 + fixed_separation / 2.0,
        arena.width,
        arena.height / 2.0,
    )
    return circle_l, circle_r


def save_info_map_plot(info_mat, output_path: Path, width_label: str):
    fig, ax = plt.subplots(figsize=(6, 5))
    image = ax.imshow(info_mat, cmap="cividis", origin="lower", aspect="auto")
    min_val = info_mat.min()
    max_val = info_mat.max()
    ax.set_title(
        f"Unnormalized Info Map (aperture width={width_label})\nmin={min_val:.3f}, max={max_val:.3f}"
    )
    ax.set_xlabel("Y index")
    ax.set_ylabel("X index")
    fig.colorbar(image, ax=ax, label="Information")
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def main():
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    selected_mapping = None
    if args.game_aperture_widths is not None:
        selected_mapping = apertures_from_game_set(args.game_aperture_widths)
        args.aperture_widths = [row["infomap_aperture"] for row in selected_mapping]

        print("Using custom game apertures:")
        for row in selected_mapping:
            print(
                "  game_aperture={:.3f} | infomap_aperture={:.3f}".format(
                    row["game_aperture"],
                    row["infomap_aperture"],
                )
            )
    elif args.occlusion_shape_set is not None:
        game_set = OCCLUSION_SHAPE_SETS[args.occlusion_shape_set]
        selected_mapping = apertures_from_game_set(game_set)
        args.aperture_widths = [row["infomap_aperture"] for row in selected_mapping]

        print(f"Using occlusion shape set: {args.occlusion_shape_set}")
        for row in selected_mapping:
            print(
                "  game_aperture={:.3f} | infomap_aperture={:.3f}".format(
                    row["game_aperture"],
                    row["infomap_aperture"],
                )
            )

    arena = Arena(
        length=args.arena_length,
        width=args.arena_width,
        height=args.arena_height,
    )
    if args.y_resolution is None:
        y_resolution = int(round(arena.length - 10))
    else:
        y_resolution = args.y_resolution
    if y_resolution <= 0:
        raise ValueError(f"y_resolution must be > 0; got {y_resolution}.")

    for opening_width in args.aperture_widths:
        validate_opening_width(opening_width, arena.width)
        if np.isclose(opening_width, 0.0):
            info_mat = np.zeros((args.x_resolution, y_resolution))
        else:
            aperture = Aperture(arena=arena, opening_width=opening_width)
            circle_l, circle_r = target_circle_centers(arena)

            info_mat = info_map(
                arena=arena,
                circle1_center=circle_l,
                circle2_center=circle_r,
                aperture=aperture,
                radius=args.radius,
                x_resolution=args.x_resolution,
                y_resolution=y_resolution,
                source_height=args.source_height,
                angle_step_degrees=args.angle_step_degrees,
            )

        width_label = f"{opening_width:g}"
        output_path = args.out_dir / f"{args.prefix}_{width_label}w.npy"
        np.save(output_path, info_mat)
        print(
            f"Saved {output_path} | aperture_width={opening_width:g} "
            f"(shape={info_mat.shape})"
        )
        if args.plot:
            plot_output_path = output_path.with_suffix(".png")
            save_info_map_plot(
                info_mat=info_mat,
                output_path=plot_output_path,
                width_label=width_label,
            )
            print(f"Saved plot {plot_output_path}")


if __name__ == "__main__":
    main()

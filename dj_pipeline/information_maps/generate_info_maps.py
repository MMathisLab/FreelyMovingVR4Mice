#!/usr/bin/env python3
"""Generate unnormalized information maps for calibrated occlusion shapes.

Standalone CLI around ``vr4mice/analysis/information_maps.py``. The same maps
are computed in the pipeline by ``information_maps.InformationMap``
(``run.py info_maps``); see that module for the occlusion/visibility
calibration between game and info-map aperture units.

Input modes (exactly one):
- ``--aperture-widths``: widths in info-map arena units, e.g. 8.7 12.3 17.3.
- ``--game-aperture-widths``: widths in game units, converted with the
    calibration (e.g. 15 4 7.75 5.57 10.78).
"""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vr4mice.analysis.information_maps import (  # noqa: E402
    Arena,
    compute_info_map,
    convert_game_to_infomap_aperture,
    info_map_filename,
    save_info_map_plot,
)


def parse_args():
    """Parse CLI arguments for info-map generation.

    Note:
        `--aperture-widths` should be provided in info-map arena units. For
        standard occlusion shapes, use 8.7 (0% visible), 12.3 (10%),
        17.3 (35%), 24.5 (72%) and 34.6 (99%), which correspond to in-game
        aperture widths 3.0, 4.2, 6.0, 8.48 and 12.0 respectively.
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
        help="Aperture opening widths in info-map arena units.",
    )
    parser.add_argument(
        "--game-aperture-widths",
        type=float,
        nargs="+",
        default=None,
        help=(
            "Aperture widths in game units; values are converted to info-map "
            "arena units using calibration correspondences."
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

    if (args.aperture_widths is None) == (args.game_aperture_widths is None):
        parser.error(
            "provide exactly one of: --aperture-widths, --game-aperture-widths."
        )

    return args


def main():
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    if args.game_aperture_widths is not None:
        args.aperture_widths = []
        for game_aperture in args.game_aperture_widths:
            infomap_aperture = convert_game_to_infomap_aperture(game_aperture)
            args.aperture_widths.append(infomap_aperture)
            print(
                f"  game_aperture={game_aperture:.3f} | "
                f"infomap_aperture={infomap_aperture:.3f}"
            )

    arena = Arena(
        length=args.arena_length,
        width=args.arena_width,
        height=args.arena_height,
    )

    for infomap_aperture in args.aperture_widths:
        info_map = compute_info_map(
            infomap_aperture=infomap_aperture,
            arena=arena,
            radius=args.radius,
            x_resolution=args.x_resolution,
            y_resolution=args.y_resolution,
            source_height=args.source_height,
            angle_step_degrees=args.angle_step_degrees,
        )

        output_path = args.out_dir / (
            info_map_filename(infomap_aperture, prefix=args.prefix) + ".npy"
        )
        np.save(output_path, info_map)
        print(
            f"Saved {output_path} | infomap_aperture={infomap_aperture:g} "
            f"(shape={info_map.shape})"
        )
        if args.plot:
            plot_output_path = output_path.with_suffix(".png")
            save_info_map_plot(
                info_map=info_map,
                output_path=plot_output_path,
                infomap_aperture=infomap_aperture,
            )
            print(f"Saved plot {plot_output_path}")


if __name__ == "__main__":
    main()

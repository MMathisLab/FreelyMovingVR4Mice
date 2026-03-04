#!/usr/bin/env python3
import argparse
from dataclasses import dataclass
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from utils import info_map


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
        required=True,
        help="Aperture opening widths in arena units.",
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
    return parser.parse_args()


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

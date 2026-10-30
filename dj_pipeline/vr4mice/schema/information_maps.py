"""Information map schema: target visibility across the arena per occlusion level."""

import datajoint as dj
import numpy as np

from vr4mice.analysis import information_maps
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

schema_name = "information_maps"
schema = get_schema(schema_name, locals())
logger = Logger.get_logger()


@schema
class OcclusionAperture(dj.Lookup):
    """
    OcclusionAperture definition table:
    occluder aperture widths (game units) to compute information maps for.
    To add a map, add a row to ``contents`` and run ``run.py info_maps``.
    """

    definition = """
    game_aperture : decimal(5,2)    # occluder aperture width in game units
    ---
    visible_percent = null : int16  # percent of target visible, if known
    """

    contents = [
        # Calibrated occlusion levels (contrast tasks)
        (3.0, 0),
        (4.2, 10),
        (6.0, 35),
        (8.48, 72),
        (12.0, 99),
        # Shape task occluders: percent inferred from the contrast calibration,
        # matching the shape_figures notebooks; 5.0 and 8.0 linearly interpolated
        (4.0, 8),
        (5.0, 21),
        (5.57, 29),
        (7.75, 62),
        (8.0, 65),
        (10.78, 93),
        (15.0, 100),  # beyond the 12.0 calibration point, saturated
    ]


def sync_lookup_contents():
    """Insert Lookup rows from class ``contents`` that are missing in the DB.

    DataJoint only loads ``contents`` when a Lookup table is first created, so
    apertures added to ``contents`` later must be back-filled.
    """
    OcclusionAperture.insert(OcclusionAperture.contents, skip_duplicates=True)


@schema
class InformationMap(dj.Computed):
    """
    InformationMap definition table:
    unnormalized information map for one occlusion level
    """

    definition = """
    -> OcclusionAperture
    ---
    visible_percent = null : int16  # percent of target visible, copied from OcclusionAperture
    infomap_aperture : float64      # aperture width converted to info-map arena units
    info_map : <blob>               # unnormalized info map, (x_resolution, y_resolution)
    """

    def make(self, key):
        """Compute the info map for one aperture with the default arena geometry."""
        visible_percent = (OcclusionAperture & key).fetch1("visible_percent")
        if visible_percent != visible_percent:  # null may come back as NaN
            visible_percent = None
        game_aperture = float(key["game_aperture"])
        infomap_aperture = information_maps.convert_game_to_infomap_aperture(
            game_aperture
        )
        info_map = information_maps.compute_info_map(
            infomap_aperture=infomap_aperture,
            arena=information_maps.ARENA,
            show_progress=False,
        )

        logger.info(
            "Computed info map for %s",
            information_maps.aperture_label(
                infomap_aperture, game_aperture, visible_percent
            ),
        )

        self.insert1(
            {
                **key,
                "visible_percent": visible_percent,
                "infomap_aperture": infomap_aperture,
                "info_map": info_map,
            }
        )

    def select(self, game_aperture=None, visible_percent=None):
        """Restrict to one map by game aperture width or by percent visible.

        With neither argument, ``self`` must already be restricted to one map.
        """
        if game_aperture is not None and visible_percent is not None:
            raise ValueError("Give either game_aperture or visible_percent, not both.")
        if game_aperture is not None:
            restricted = self & {"game_aperture": game_aperture}
        elif visible_percent is not None:
            restricted = self & {"visible_percent": visible_percent}
        else:
            restricted = self
        if len(restricted) != 1:
            raise ValueError(
                f"Expected exactly one info map for game_aperture={game_aperture}, "
                f"visible_percent={visible_percent}; found {len(restricted)}. "
                f"Available:\n{OcclusionAperture()}"
            )
        return restricted

    def plot(self, game_aperture=None, visible_percent=None, **plot_kwargs):
        """Plot one info map, selected by game aperture width or percent visible.

        ``InformationMap().plot(game_aperture=4.2)`` and
        ``InformationMap().plot(visible_percent=10)`` plot the same map.
        ``plot_kwargs`` go to ``information_maps.plot_info_map``, e.g. to draw
        a normalized map as a trajectory background::

            InformationMap().plot(
                game_aperture=4.2, ax=ax, normalize_by=max_value,
                rig_coordinates=True, title=False, colorbar=False,
                cmap="bone", zorder=-10,
            )

        Returns the matplotlib figure; save it with ``fig.savefig(path)``.
        """
        entry = self.select(game_aperture, visible_percent).fetch1()
        print(
            information_maps.aperture_label(
                entry["infomap_aperture"],
                entry["game_aperture"],
                entry["visible_percent"],
            )
        )
        return information_maps.plot_info_map(
            entry["info_map"],
            entry["infomap_aperture"],
            entry["game_aperture"],
            entry["visible_percent"],
            **plot_kwargs,
        )

    def get_info_at_position(
        self, x, y, game_aperture=None, visible_percent=None, normalize_by=None
    ):
        """Info at rig position(s) (x, y) for one map, divided by ``normalize_by``.

        Vectorized: pass whole columns, e.g.
        ``InformationMap().get_info_at_position(df.x, df.y, game_aperture=4.2)``.
        """
        info_map = self.select(game_aperture, visible_percent).fetch1("info_map")
        return information_maps.info_at_position(
            info_map, x, y, normalize_by=normalize_by
        )

    def get_info_for_dataframe(
        self,
        df,
        aperture_to_map=None,
        normalize_by=None,
        aperture_column="aperture",
        x_column="x",
        y_column="y",
    ):
        """Info at each row's (x, y), from the map of the row's aperture.

        Rows are matched to maps on ``game_aperture`` (rounded to 2 decimals).
        ``aperture_to_map`` maps task apertures that have no map of their own
        to one, e.g. ``{4.3: 4.2}``. Rows without a map get NaN and are logged.

        Example::

            df["info_gain"] = info_maps.get_info_for_dataframe(
                df, aperture_to_map={4.3: 4.2}, normalize_by=max_value
            )

        Returns:
            Array of info values aligned with the rows of ``df``.
        """
        task_apertures = df[aperture_column].astype(float).round(2).to_numpy()
        map_apertures = task_apertures.copy()
        for task_aperture, map_aperture in (aperture_to_map or {}).items():
            map_apertures[task_apertures == round(float(task_aperture), 2)] = round(
                float(map_aperture), 2
            )

        available = {round(float(a), 2) for a in self.fetch("game_aperture")}
        x = df[x_column].to_numpy()
        y = df[y_column].to_numpy()
        info = np.full(len(df), np.nan)
        for map_aperture in np.unique(map_apertures[~np.isnan(map_apertures)]):
            if map_aperture not in available:
                continue
            rows = map_apertures == map_aperture
            info[rows] = self.get_info_at_position(
                x[rows],
                y[rows],
                game_aperture=float(map_aperture),
                normalize_by=normalize_by,
            )

        missing = sorted(set(map_apertures[np.isnan(info)]) - available)
        if missing:
            logger.warning(
                "No info map for apertures %s (available: %s): info set to NaN",
                missing,
                sorted(available),
            )
        return info

    def max_info(self):
        """Max info value across the maps in ``self``, to normalize them jointly.

        Restrict first to the maps being compared, e.g.
        ``(InformationMap & [{"game_aperture": 4.2}, {"game_aperture": 12.0}]).max_info()``.
        """
        return max(info_map.max() for info_map in self.fetch("info_map"))

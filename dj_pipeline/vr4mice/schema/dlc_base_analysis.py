import datajoint as dj

from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

from .base_analysis import insert_send_email

schema_name = "dlc_base_analysis"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()


@schema
class TrackingSummaryPlots(dj.Computed):
    definition = """
    -> vr4mice.Dataset
    ---
    filename:  varchar(255)
    """

    def make(self, key, send=False):
        """
        key: Dataset
        """
        # generate

        from vr4mice.analysis.tracking_summary_dj import plot_keypoints_summary
        from vr4mice.schema import base, dlc

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        if dlc.DLCKptsDf & key:
            full_path = plot_keypoints_summary(key, save_path="/data/summary_plots")
        else:
            logger.warning(
                "Populate first DLC DLCKptsDf for "
                + str(key)
                + "; call DLCKptsDf.populate();"
            )
            return False

        data = {**key, **{"filename": full_path}}
        key = (base.Base() & key).fetch(as_dict=True)[0]

        insert_send_email(key, data, TrackingSummaryPlots(), full_path, send=send)

import glob
import os
from typing import List

import datajoint as dj
import joblib
from vr4mice.utils.logger import Logger
from vr4mice.utils.helpers.filepath import get_filename
from vr4mice.utils.maushaus_utils import extract_video_info, path_in_store

logger = Logger.get_logger()


def parallel_populate_videos(
    paths: List[str],
    dataset: str,
    n_jobs: int = -1,
    skip_duplicates: bool = True,
):
    """
    Populate videos into the database in Parallel
    :param paths: List of video paths to populate
    :param dataset: Dataset name, must be in maushaus.Dataset table
    :param n_jobs: number of processes to spawn. -1 uses all available CPUs
    :param skip_duplicates: if True, no error is thrown if a video is duplicated
    :return:
    """

    @joblib.delayed
    def worker(filepath, dj_config):

        worker_logger = Logger.get_logger()
        dj.config.update(dj_config)
        from maushaus.schema import maushaus

        filename = get_filename(filepath)
        try:
            maushaus.Video.populate_from_file(dataset,
                                              filepath,
                                              skip_duplicates=skip_duplicates)
        except ValueError:
            worker_logger.warning(
                f"file {filename} does not match naming conventions, Skipping.."
            )
            return filename

        worker_logger.info(f"successfully populated video_file {filename}")

    dj_config = dict(dj.config)

    ret_paths = joblib.Parallel(n_jobs=n_jobs)(worker(video_path, dj_config)
                                               for video_path in paths)

    failed_paths = [filename for filename in ret_paths if filename is not None]
    logger.info(f"""Summary:
                        Successfully populated {len(ret_paths) - len(failed_paths)} video files
                        from dataset {dataset}""")

    if len(failed_paths) > 0:
        logger.warning(f"Skipped {len(failed_paths)} files which are: \n"
                       "\n".join(failed_paths))


def populate_videos_in_folder(folder_path: str,
                              dataset: str,
                              max: int = -1,
                              n_jobs: int = -1,
                              skip_duplicates: bool = True):

    paths = glob.glob(os.path.join(folder_path, "*"))
    if max != -1:
        paths = paths[:max]

    parallel_populate_videos(
        paths=paths,
        dataset=dataset,
        n_jobs=n_jobs,
        skip_duplicates=skip_duplicates,
    )


def populate_videos(paths: list,
                    dataset: str,
                    max: int = -1,
                    n_jobs: int = -1,
                    skip_duplicates: bool = True):
    parallel_populate_videos(
        paths=paths,
        dataset=dataset,
        n_jobs=n_jobs,
        skip_duplicates=skip_duplicates,
    )

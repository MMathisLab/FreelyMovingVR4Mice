"""
Manual ingest into the FreelyMovingVR4Mice pipeline.
"""

from vr4mice.ingest.data_loading import NormalizedData
from vr4mice.ingest import table_transforms
from vr4mice.ingest.auto_fill import autofill_table
from pydantic import validate_call
from pathlib import Path

from vr4mice.utils.logger import Logger


logger = Logger.get_logger()


@validate_call
def fill_from_dataset(data: dict, **dj_kwargs):
    """
    This uses the pickle data and associated files.
    """
    for module, table_names in table_transforms.fill_tables.items():
        logger.info("auto_fill ingesting module: ", module.__name__)
        nesting_transform = table_transforms.data_nesting[module]
        for table_name in table_names:
            logger.info("auto_fill ingesting table: ", table_name)
            table = getattr(module, table_name)
            if table_name not in nesting_transform:
                autofill_table(table, data=data, **dj_kwargs)
            else:
                post_transformed_data = nesting_transform[table_name](data)
                autofill_table(table, data=post_transformed_data, **dj_kwargs)


@validate_call
def fill_for(
    dataset_name: str, teensy_dir: Path, videos_dir: Path, **dj_kwargs
):
    """
    This finds a teensy pickle file and associated files using the dataset_name and directories provided.
    """

    teensy_path = teensy_dir / f"{dataset_name}.pickle"
    normalized_data = NormalizedData(
        teensy_filepath=teensy_path, related_dir=videos_dir
    )
    export_data = normalized_data.export()

    fill_from_dataset(data=export_data, **dj_kwargs)


@validate_call
def fill_all_in_dir(
    teensy_dir: Path,
    videos_dir: Path,
    ignore_errors=False,
    tqdm=None,
    **dj_kwargs,
):
    """
    teensy_dir: Directory to the teensy data pickle files
    videos_dir: Directory to the related files
    ignore_errors: Will skip datasets that have errors and will print them out
    tqdm: Can provide a tqdm object,
        either `from tqdm import tqdm`
        or `from tqdm.notebook import tqdm`
    """

    from vr4mice.schema import (
        vr4mice,
    )  # Needed to check against the vr4mice.Dataset table

    if tqdm is None:

        def tqdm(x):
            return x

    already_ingested_datasets = set(vr4mice.Dataset.proj().fetch("dataset"))
    teensy_dataset_names = {path.stem for path in teensy_dir.glob("*.pickle")}
    remaining_datasets = teensy_dataset_names.difference(already_ingested_datasets)

    for dataset_name in tqdm(remaining_datasets):
        if ignore_errors:
            try:
                fill_for(
                    dataset_name,
                    teensy_dir=teensy_dir,
                    videos_dir=videos_dir,
                    **dj_kwargs,
                )
            except Exception as e:
                print(f"Error in {dataset_name}:")
                print(e)
        else:
            fill_for(
                dataset_name,
                teensy_dir=teensy_dir,
                videos_dir=videos_dir,
                **dj_kwargs,
            )

"""
    This script contains functions wrappers for plotting.py script:
    It fetches the columns from database tables that are only required for a function,
    Instead of fetching the whole table that is heavy as contians multiple longblobs
"""
from vr4mice.analysis import plotting
from vr4mice.schema import vr4mice, base_analysis, dlc
from typing import List


def plot_box_rectangle(
    box_label: str,
    datasets_keys: List = [],
    edgecolor: str = "#009B9E",
    fill: bool = False,
    alpha: float = 0.6,
    linewidth: int = 4,
):
    """{box_label}_box_x_min: The minimum x-coordinate of the box.
       {box_label}_box_x_max: The maximum x-coordinate of the box.
       {box_label}_box_z_min: The minimum z-coordinate of the box.
       {box_label}_box_z_max: The maximum z-coordinate of the box.

       session_labels: contains ensemble of datasets that we would like to fetch.

    """
    df = None
    columns = [f"{box_label}_box_x_min",  f"{box_label}_box_x_max", 
            f"{box_label}_box_z_min", f"{box_label}_box_z_max"]
    
    if len(datasets_keys) == 0:
        df = base_analysis.BoxDataFrame().get_all_data(columns)

    # TODO: case with fetching per dataset

    if df:
        print(df)
        #plotting.plot_box_rectangle(df, box_label, edgecolor, fill, alpha, linewidth)
    else:
        print(df)
        print(datasets_keys)


 

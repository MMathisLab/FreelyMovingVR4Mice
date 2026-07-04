import datetime
import os
import sys

import datajoint as dj
import numpy as np
from base_schemas.schemas import exp, mice

from vr4mice.utils.logger import Logger

"""
    Script that fetches the data from database 
    to create a dictionary that will be used in the GUI's dropdown menus 
"""


def _create_mice_dict(all_mice: dict) -> dict:
    """
    Create a dictionary of mice with their relevant information.

    Args:
      all_mice (dict): A dictionary containing data fetched from mice tables (alive mouse only).

    Returns:
      dict: A dictionary with each mouse's name as the key and its relevant information as the value.
    """
    mice_dict = dict()

    for mouse_d in all_mice:
        mouse_name = mouse_d["mouse_name"]
        mice_dict[mouse_name] = mouse_d

        surgery_type = list(
            (mice.Surgery() & 'mouse_name = "%s"' % mouse_d["mouse_name"]).fetch(
                "surgery_type"
            )
        )

        mouse = mice.Mouse() & 'mouse_name = "%s"' % mouse_name
        start_date = mouse.get_starting_date()
        curr_day = mouse.get_current_day()

        # find date of last experiment
        session_incr = mouse.get_session_increment()
        if session_incr == 0:
            last_exp = None
        else:
            last_session = (
                exp.Session()
                & {"mouse_name": mouse_name}
                & {"session_increment": session_incr - 1}
            )
            last_exp = last_session.fetch("doe")[0]

        mice_dict[mouse_name]["start_date"] = start_date
        mice_dict[mouse_name]["day"] = curr_day
        mice_dict[mouse_name]["last_exp"] = last_exp
        mice_dict[mouse_name]["surgery_type"] = surgery_type

    return mice_dict


def _fetch_alive_mice() -> list:
    """
    Return Mouse rows excluding sacrificed and breeding mice.

    DJ 2.x rejects chained table subtraction (Mouse - Sacrificed - Breed) because
    mouse_name has incompatible lineages across dependent tables.
    """
    excluded = {
        *mice.Sacrificed().fetch("mouse_name"),
        *mice.Breed().fetch("mouse_name"),
    }
    return [
        row
        for row in mice.Mouse().fetch(as_dict=True)
        if row["mouse_name"] not in excluded
    ]


def fetch_tables() -> dict:
    """
    Fetches tables from the VR4Mice database and returns a dictionary containing the fetched data.

    Returns:
    A dictionary containing the fetched data from the following tables:
    Keys of the dictionary correspond to the name of the table in the datajoint table definitions
    or to the attribute, if only attribute is fetched
    Example:

    - experimenter_name: a list of all experimenter names fetched from the Experimenter table
    - Anesthesia: a dictionary containing all rows fetched from the Anesthesia table
    - Rig: a dictionary containing all rows fetched from the Rig table
    ...
    Particular keys common for all pipelines:
    - MouseDict: a dictionary created from the result of fetching all mice from the Mouse table, excluding the Sacrificed and Breed tables
    - timestamp: the current date and time, represented as a datetime object

    Note:
    - The 'Mouse' table has been commented out, as there is no use to share all mice raw entries (as we have MouseDict)
    - Some tables have 'LT' comments next to them, indicating that they are Lookup tables
    - Some tables have been commented out entirely, indicating that they are not currently used in the pipeline

    """
    all_mice = _fetch_alive_mice()

    return {
        # 'Mouse': all_mice,
        "MouseDict": _create_mice_dict(all_mice),
        "experimenter_name": list(exp.Experimenter().fetch("experimenter_name")),
        "Anesthesia": exp.Anesthesia().fetch(as_dict=True),  # LT
        "Rig": exp.Rig().fetch(as_dict=True),  # LT
        "OptogeneticsRegion": exp.OptogeneticsRegion().fetch(as_dict=True),  # LT
        "OptogeneticsTiming": exp.OptogeneticsTiming().fetch(as_dict=True),  # LT
        "OptogeneticsVariant": exp.OptogeneticsVariant().fetch(as_dict=True),  # LT
        "opto_name": list(exp.Optogenetics().fetch("opto_name")),
        # 'force_field_name': list(exp.ForceField().fetch('force_field_name')),
        # 'strength': list(exp.ForceField().fetch('strength')),
        "Task": exp.Task().fetch(as_dict=True),
        "task_type": exp.Task().get_pipeline_task_names("ar"),
        # 'Joystick': list(exp.Joystick().fetch('joystick_name')),
        # 'surgery_type': list(mice.SurgeryType().fetch('surgery_type')),
        "MouseLicensing": mice.MouseLicensingGeneva().fetch(as_dict=True),  # LT
        "MouseScoreSheet_BodyCondition": mice.MouseScoreSheet_BodyCondition().fetch(
            as_dict=True
        ),  # LT
        "MouseScoreSheet_GeneralAssay": mice.MouseScoreSheet_GeneralAssay().fetch(
            as_dict=True
        ),  # LT
        "MouseScoreSheet_HousingAssesment": mice.MouseScoreSheet_HousingAssesment().fetch(
            as_dict=True
        ),  # LT
        "timestamp": datetime.datetime.now(),
    }


def fetch_data(dst="./test_menu.npy"):
    """
    Fetches data from the database and saves it as a numpy file.

    Args:
    dst (str): The path where the numpy file will be saved. Defaults to './test_menu.npy'.

    Note:
    The path is accessed in the context of docker.
    """
    data = fetch_tables()
    np.save(dst, data)

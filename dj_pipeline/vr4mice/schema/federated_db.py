from pathlib import Path

import datajoint as dj
import pandas as pd
from base_schemas.schemas import exp, mice

from vr4mice.schema import vr4mice
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

schema_name = "federated_db"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()


@schema
class VR4Mice(dj.Manual):
    """
    VR4Mice definition table:
    links together Dataset with base Mouse, Exp schemas
    """

    definition = """
    -> vr4mice.Dataset
    ---
    -> mice.Mouse
    -> exp.Session
    """

    # TODO: make call to populate mice and exp, based on gui output (if exists) from path from Dataset

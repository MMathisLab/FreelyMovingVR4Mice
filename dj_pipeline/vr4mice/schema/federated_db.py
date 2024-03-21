from base_schemas.schemas import exp
from base_schemas.schemas import mice

import datajoint as dj
from pathlib import Path

from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

from vr4mice.schema import vr4mice
import pandas as pd

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

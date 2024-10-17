from pathlib import Path

import datajoint as dj
import pandas as pd
import re
from base_schemas.schemas import exp, mice
from vr4mice.schema import vr4mice
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

schema_name = "base"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()


@schema
class Base(dj.Computed):
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

    def make(self, key):
        try:
            data = parse_filename(key["dataset"])

            mouse_key = {"mouse_name": data["mouse_name"]}

            if mice.Mouse() & mouse_key:
                pk = mice.Mouse().primary_key
                mouse = (mice.Mouse() & mouse_key).fetch(*pk, as_dict=True)[0]

            session_key = {"date": data["date"], "attempt": data["attempt"]}

            if exp.Session() & mouse_key & session_key:
                pk = exp.Session().primary_key
                session = (exp.Session() & mouse_key & session_key).fetch(
                    *pk, as_dict=True
                )[0]
            data = {**key, **mouse, **session}
            self.insert1(data, allow_direct_insert=True)
            logger.info(f"{self.__class__.__name__} populated for {key}.")

        except Exception as err:
            err = f"Error while populating the {self.__class__.__name__} table: \
                    key: {key} \n {err}"
            logger.warning(err)


def parse_filename(filename):
    pattern = r"^(?P<name>[A-Za-z]+)_(?P<date>\d{4}-\d{2}-\d{2})_(?P<attempt>\d+)$"
    match = re.match(pattern, filename)

    if match:
        name = match.group("name")
        date = match.group("date")
        attempt = match.group("attempt")
        return {
            "mouse_name": name,
            "date": date,
            "attempt": int(attempt),  # Convert attempt to an integer
        }
    else:
        raise ValueError("Filename does not match the expected format.")

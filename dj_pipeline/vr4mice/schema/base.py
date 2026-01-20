"""Base schema linking datasets to shared experiment metadata."""

import re
from pathlib import Path

import datajoint as dj
import pandas as pd
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
        """Link a dataset to mouse and experiment session metadata."""
        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            data = parse_filename(key["dataset"])

            mouse_key = {"mouse_name": data["mouse_name"]}

            if mice.Mouse() & mouse_key:
                pk = mice.Mouse().primary_key
                mouse = (mice.Mouse() & mouse_key).proj(*pk).to_dicts()[0]

            session_key = {"doe": data["date"], "attempt": data["attempt"]}

            if exp.Session() & mouse_key & session_key:
                pk = exp.Session().primary_key
                session = (exp.Session() & mouse_key & session_key).proj(
                    *pk
                ).to_dicts()[0]
            else:
                logger.warning(f"{self.__class__.__name__} no Session entry for {key}.")
                return
            data = {**key, **mouse, **session}
            self.insert1(data, allow_direct_insert=True)
            logger.info(f"{self.__class__.__name__} populated for {key}.")

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)


def parse_filename(filename):
    """Parse dataset filename into mouse name, date, and attempt."""
    pattern = r"^(?P<name>[A-Za-z\d]+)_(?P<date>\d{4}-\d{2}-\d{2})_(?P<attempt>\d+)$"
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

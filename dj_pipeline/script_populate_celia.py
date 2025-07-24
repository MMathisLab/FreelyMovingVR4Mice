from base_actions.connect import connect
connect()

from vr4mice.utils.logger import Logger
logger = Logger.get_logger()


from vr4mice.schema.vr4mice import SignalsPhotodiode

SignalsPhotodiode().populate({"dataset": "Jacana_2024-07-26_1"},
                             suppress_errors = True)
from base_actions.connect import connect
connect()

from vr4mice.schema.vr4mice import SignalsPhotodiode
SignalsPhotodiode().populate({"dataset": "Jacana_2024-07-26_1"})
from base_schemas.schemas import mice, exp
from vr4mice.actions.helpers_dj import get_session_incr, no_value, default
"""
    Skeleton of base_schemas (mice, exp) datajoint tables definitions used for the population:
    Define tables, attributes and order of population
"""

local_def = {
    'session_increment': get_session_incr,
    'joystick_name': no_value,
    'force_field_name': no_value,
    #'opto_name': no_value_opto,
    'pulse_frequency': default,
    'pulse_length': default,
    'laser_power': default,
}

# KEYS #
session = [
    'mouse_name',  #
    'day',  #
    'attempt',  #
    'doe',
    'session_increment',
    'rig_id',
    'experimenter_name',
    'anesthesia_name',
    'opto_name',
    'task_name',
    'force_field_name',
    'joystick_name',
    'session_notes',
]

score_sheet = [
    'mouse_name',  #
    'license',
    'general_assay',
    'housing_assay',
    'body_condition',
    'doc',
]
scores_sheet_water = [
    'mouse_name',
    'doc',
    'weight_percentage',
]

session_score_sheet = [
    'mouse_name',
    'day',
    'attempt',
    'doc',
]

opto = [
    'opto_name',
    'pulse_frequency',
    'pulse_length',
    'laser_power',
    'opto_region_name',
    'opto_timing_name',
    'opto_variant_name',
]

tables = {
    "Optogenetics": opto,
    "Session": session,
    "MouseScoreSheet": score_sheet,
    "MouseScoreSheet_WaterRestriction": scores_sheet_water,
    "SessionScoreSheet": session_score_sheet,
}

dj_tables = {
    "MouseScoreSheet": mice.MouseScoreSheet(),
    "MouseScoreSheet_WaterRestriction":
    mice.MouseScoreSheet_WaterRestriction(),
    "SessionScoreSheet": exp.SessionScoreSheet(),
    "Optogenetics": exp.Optogenetics(),
    "Session": exp.Session(),
    "Mice": mice.Mouse(),
}

transformer = {}

base = {
    "tables": tables,
    "dj_tables": dj_tables,
    "local_def": local_def,
    "transformer": transformer
}

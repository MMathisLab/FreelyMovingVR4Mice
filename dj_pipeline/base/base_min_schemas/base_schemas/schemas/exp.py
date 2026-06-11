import datajoint as dj
from base_schemas.schemas import mice

"""
    Minimal Schema version for experimental information
"""

schema = dj.Schema("exp", locals(), create_tables=True)


@schema
class Experimenter(dj.Lookup):
    definition = """  # Information about Experimenter

    experimenter_name      : char(20)   # lab member in lower case
    ---
    full_name              : varchar(255)    # Full name (FirstName LastName)
    mail                   : varchar(128)    # email: default None (not showing in contents but in the database)
    """

    contents = [["user", "Test User", ""]]


@schema
class Anesthesia(dj.Lookup):
    definition = """   #  anesthesia states
    anesthesia_name             : varchar(20) # anesthesia short name
    ---
    anesthesia_details = ''     : varchar(1024) # longer description
    """
    contents = [
        ["awake", "mouse is awake and no immediate hx of anesthesia"],
    ]


@schema
class Rig(dj.Lookup):
    definition = """
    rig_id        : int             # Experimental setup number
    ---
    details       : varchar(2048)   # Description of the setup
    """
    contents = [
        [1, "AR"],
    ]


@schema
class OptogeneticsRegion(dj.Lookup):
    definition = """  # Optogenetics applied

    opto_region_name          : char(10)   # region
    -----
    opto_region_details = ''  : varchar(2048)   # brain region
    """
    contents = [
        ["none", "no optogenetics was applied during the session"],
    ]


@schema
class OptogeneticsTiming(dj.Lookup):
    definition = """  # timing of the optogenetics in joystick tasks only

    opto_timing_name          : varchar(20)     # short name for the timing
    -----
    opto_timing_details = ''  : varchar(2048)   # details about timing
    """
    contents = [
        ["none", ""],
    ]


@schema
class OptogeneticsVariant(dj.Lookup):
    definition = """  # Type of expressed channel
    opto_variant_name          : char(10)       # optogenetic variant short name
    -----
    opto_variant_details = ''  : varchar(2048)  # details about the variant
    """
    contents = [
        ["none", "no optogentics used"],
    ]


@schema
class Optogenetics(dj.Lookup):
    definition = """  # Optogenetics used in the session

    opto_name     : char(128)   # optogenetic protocol abbreviation
    -----
    pulse_frequency    : double      # Pulse frequency in Hz
    pulse_length       : double      # Pulse length in ms
    laser_power        : double      # Input power at laser tip in mW
    -> OptogeneticsRegion
    -> OptogeneticsTiming
    -> OptogeneticsVariant
    """
    contents = [
        ["none", -1, -1, -1, "none", "none", "none"],
    ]


@schema
class Task(dj.Lookup):
    definition = """  # Information about the performed task
    task_name          : char(100)
    ---
    task_details = ''  : varchar(2048)
    """

    __ar_tasks = [
        [
            "AR_visual_discrimination",
            "mouse in AR has to decide which side a white cube is on by reporting its location at the lick port",
        ]
    ]
    contents = [
        *__ar_tasks,
    ]

    __pipeline_to_tasks = {
        "ar": __ar_tasks,
    }

    @classmethod
    def get_pipeline_task_names(cls, pipeline_name):
        return [task[0] for task in cls.__pipeline_to_tasks[pipeline_name]]


@schema
class Session(dj.Manual):
    definition = """ # Experimental session
    -> mice.Mouse
    day       : int       # days after start of the experiment
    attempt   : int       # counter for sessions on same day (usually 1)
    ---
    doe : date          # date of the Session
    session_increment  : int           # counter of consecutive sessions for each mouse (manually)
    -> Rig              # links to the tables defining details of the session
    -> Experimenter
    -> Anesthesia
    -> Optogenetics
    -> Task
    session_notes = ""              : varchar(4095)       # free-text notes
    session_ts = CURRENT_TIMESTAMP  : timestamp           # automatic
    """

    @classmethod
    def get_sessions_for_pipeline(cls, pipeline_name):
        return cls & [
            "task_name = '{}'".format(task)
            for task in Task.get_pipeline_task_names(pipeline_name)
        ]


@schema
class SessionScoreSheet(dj.Manual):
    definition = """
    -> Session
    ---
    -> mice.MouseScoreSheet
    -> mice.MouseScoreSheet_WaterRestriction
    """

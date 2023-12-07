"""
    Minimal Schema version for experimental information
"""

import pathlib
import os

import datajoint as dj
import PIL.Image
from base_schemas.utils import datastore

schema = dj.schema('mice', locals(), create_tables=True)


@schema
class Strain(dj.Lookup):

    definition = """    # Genetic type of the mouse
    strain          : char(128) # mouse variant short name
    ---
    formal_name     : varchar(2048)
    stock_number    : varchar(255)
    """
    contents = [
        ['N/A', 'N/A', 'N/A'],
    ]


@schema
class Mouse(dj.Manual):

    definition = """ 
      mouse_name    : varchar(128)             # name of mouse (unique)
      ---
      mouse_id      : int                      # unique mouse id, ATTENTION: take care that this is really unique
      dob           : date                     # day of birth (year-month-day)
      sex           : enum('M', 'F', 'U')      # sex of mouse - Male, Female, or Unknown/Unclassified
      -> Strain                                # link to the genetic type of the mouse
      """

    def get_starting_date(self):
        """
        Returns the starting date of the first experiment in the current query result.

        Returns:
        datetime.date or None: The starting date of the first experiment in the current query result,
            or None if there are no experiments in the result.

        Raises:
        Exception: If the query result corresponds to more than one mouse.

        Notes:
        - This function assumes that the current object is a DataJoint query result.
        - The query result is expected to correspond to only one mouse,
            so an exception will be raised if it corresponds to more than one.
        - This function relies on a Session table defined in the same module as this function,
            so it must be imported after Session has been defined.
        - The starting date is determined by finding the
            minimum date of all the experiments in the query result.
        """

        if len(self) != 1: # Check if self corresponds only to a single mouse
            raise Exception('Query resulted in %i mice! Only 1 result allowed...' % len(self))

        from . import exp

        daysOfExperiments = (exp.Session() & self).fetch('doe')
        if len(daysOfExperiments) > 0:
            startDate = min(daysOfExperiments)
        else:
            startDate = None

        return startDate

    def get_current_day(self):
        """
        Returns the current day of the current mouse's experiments.

        Returns:
        int: The current day of the current mouse's experiments, starting from 1.

        Notes:
        - This function assumes that the current object is a DataJoint query result.
        - The current day is calculated based on the starting date of the mouse's experiments and the current date.
        - If there are no experiments in the current query result, the current day is assumed to be 1.
        """
        startDate = self.get_starting_date()
        if startDate == None:
            return 1

        import datetime
        dateToday = datetime.date.today()
        return (dateToday - startDate).days + 1

    def get_session_increment(self):
        """
        Returns the session increment for the next session of the current mouse.

        Returns:
        int: The session increment for the next session of the current mouse.

        Raises:
        Exception: If the query result corresponds to more than one mouse.

        Notes:
        - This function assumes that the current object is a DataJoint query result.
        - The query result is expected to correspond to only one mouse,
            so an exception will be raised if it corresponds to more than one.
        - This function relies on a Session table defined in the same module as this function,
            so it must be imported after Session has been defined.
        - The session increment is determined by finding the maximum session increment
            of all the sessions in the query result and adding 1.
        - If there are no sessions in the current query result, the session increment is assumed to be 0.
        """

        if len(self) != 1: # Check if self corresponds only to a single mouse
            raise Exception('Query resulted in %i mice! Only 1 result allowed...' % len(self))

        from . import exp

        sessionNumbers = (exp.Session() & self).fetch('session_increment')
        if len(sessionNumbers) > 0:
            return max(sessionNumbers) + 1
        else:
            return 0


@schema
class SurgeryType(dj.Lookup):

    definition = """  
    surgery_type    : varchar(128) # surgery short name
    ---
    """
    contents = [
        ['N/A'],
    ]


@schema
class Surgery(dj.Manual):

    definition = """ # Details about the surgery
    -> Mouse
    ---
    -> SurgeryType                          # link to type of surgery
    surgery_details     : varchar(1024)     # descritpion of the aim of the surgery
    surgery_date=None   : varchar(256)      # date of the surgery
    """


@schema
class Sacrificed(dj.Manual):

    definition = """ # table to keep the record for sacrifice.Also, not to show in the dropdown menu!
    -> Mouse
    ---
    date_of_sacrifice   : datetime      # date of sacrifice
    reason              : varchar(2048) # comments about the reason of sacrifice
    """


@schema
class Breed(dj.Manual):

    definition = """ # table to keep the record for breeding. Also, not to show in the dropdown menu!
    -> Mouse
    ---
    """


@schema
class MouseLicensingGeneva(dj.Lookup):

    definition = """
    license   : varchar(128) # licensing name
    ---
    informal_title     : varchar(2048)
    """
    contents = [
        ['N/A', 'default licence'],
    ]


@schema
class MouseScoreSheet_BodyCondition(dj.Lookup):

    definition = """ 
    
    body_condition   : varchar(128) # short body condition name
    ---
    define_score     : varchar(2048)
    
    """
    contents = [
        ['BodyCondition1', 'emaciated'],
        ['BodyCondition2', 'under-conditioned'],
        ['BodyCondition3', 'well-conditioned'],
        ['BodyCondition4', 'over-conditioned'],
        ['BodyCondition5', '5 obese'],
    ]


@schema
class MouseScoreSheet_GeneralAssay(dj.Lookup):

    definition = """ 
    general_assay   : varchar(128) # general assay score name
    ---
    define_score     : varchar(2048)
    """
    contents = [
        ['Assay1', '1 or less euthanize cannot not aroused'],
        ['Assay2', '2 or less euthanize unable to rouse without large stim'],
        ['Assay3', '3 not groomed slow movements'],
        ['Assay4', '4 slightly lethargic'],
        ['Assay5', '5 normal behavior'],
    ]


@schema
class MouseScoreSheet_HousingAssesment(dj.Lookup):

    definition = """
    housing_assay   : varchar(128) # general assay score name
    ---
    define_score     : varchar(2048)
    """
    contents = [
        ['Yes', 'animal built housing as normal'],
        ['No', 'watch animal for signs of stress'],
    ]


@schema
class MouseScoreSheet_WaterRestriction(dj.Manual):

    definition = """ 
    -> Mouse
    doc : date          # date of check
    ---
    weight_percentage   :   varchar(128)   # percentage change from baseline
    """


@schema
class MouseScoreSheet(dj.Manual):

    definition = """ 
    -> Mouse
    doc : date          # date of check
    ---
    -> MouseLicensingGeneva
    -> MouseScoreSheet_BodyCondition
    -> MouseScoreSheet_GeneralAssay
    -> MouseScoreSheet_HousingAssesment
    """

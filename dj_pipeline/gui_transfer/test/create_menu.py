import numpy as np
import datetime

data = {
    'MouseDict': {
        'Testmouse': {
            'mouse_name': 'Testmouse',
            'mouse_id': 93,
            'dob': datetime.date(2022, 7, 23),
            'sex': 'F',
            'strain': 'WT',
            'start_date': None,
            'day': 1,
            'last_exp': None,
            'surgery_type': []
        }
    },
    'experimenter_name': ['test_exp'],
    'Anesthesia': [
        {'anesthesia_name': 'awake', 'anesthesia_details': 'mouse is awake and no immediate hx of anesthesia'},
        {'anesthesia_name': 'isoflurane', 'anesthesia_details': 'mouse is under gas anesthesia, ~4-5 Percent induction, ~1 Percent maintenance'},
        {'anesthesia_name': 'ketamine', 'anesthesia_details': 'mouse is anesthetized to near surgical plane with K/X mixture: 87.5 mg/kg Ketamine + 12.5 mg/kg Xylazine'}
    ],
    'Rig': [{'rig_id': 12, 'details': 'AR'}],
    'OptogeneticsRegion': [{'opto_region_name': 'none', 'opto_region_details': 'no optogenetics was applied during the session'}],
    'OptogeneticsTiming': [{'opto_timing_name': 'none', 'opto_timing_details': ''}],
    'OptogeneticsVariant': [{'opto_variant_name': 'none', 'opto_variant_details': 'no optogenetics used'}],
    'opto_name': ['none', 'test3', 'Mathis2017'],
    'Task': [{'task_name': 'AR_visual_discrimination', 'task_details': 'mouse in AR has to decide which side a white cube is on by reporting its location at the lick port'}],
    'task_type': ['AR_visual_discrimination'],
    'MouseLicensing': [
        {'license': 'GE1', 'informal_title': 'natural animal behavior maus haus'},
        {'license': 'GE10', 'informal_title': 'locomotor learning and VR'},
        {'license': 'GE68', 'informal_title': 'joystick forelimb motor control'}
    ],
    'MouseScoreSheet_BodyCondition': [
        {'body_condition': 'BodyCondition1', 'define_score': 'emaciated'},
        {'body_condition': 'BodyCondition2', 'define_score': 'under-conditioned'},
        {'body_condition': 'BodyCondition3', 'define_score': 'well-conditioned'},
        {'body_condition': 'BodyCondition4', 'define_score': 'over-conditioned'},
        {'body_condition': 'BodyCondition5', 'define_score': '5 obese'}
    ],
    'MouseScoreSheet_GeneralAssay': [
        {'general_assay': 'Assay1', 'define_score': '1 or less euthanize cannot be aroused'},
        {'general_assay': 'Assay2', 'define_score': '2 or less euthanize unable to rouse without large stim'},
        {'general_assay': 'Assay3', 'define_score': '3 not groomed, slow movements'},
        {'general_assay': 'Assay4', 'define_score': '4 slightly lethargic'},
        {'general_assay': 'Assay5', 'define_score': '5 normal behavior'}
    ],
    'MouseScoreSheet_HousingAssesment': [
        {'housing_assay': 'No', 'define_score': 'watch animal for signs of stress'},
        {'housing_assay': 'Yes', 'define_score': 'animal built housing as normal'}
    ],
    'timestamp': datetime.datetime(2023, 3, 3, 12, 20, 12, 62775)
}

np.save('menu.npy', data)

loaded_data = np.load('menu.npy', allow_pickle=True).item()

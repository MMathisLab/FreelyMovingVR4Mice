import logging
from PyQt5.QtWidgets import QLabel, QGridLayout, QComboBox, \
    QVBoxLayout, QCheckBox, QPlainTextEdit, QLineEdit
from PyQt5.QtCore import Qt

from utils.helpers import get_idx, get_min_len
from utils.alert import AlertMsg
from modules.template import Template
"""
    Script contains the experiment's session related GUI module 
"""

def _set_exp_labels():
    """
    Creates a dictionary of labels to be used as prompts for user input during an experiment setup.

    Returns:
        dict: A dictionary containing labels for user prompts.
    """
    return {
        "doe": "Current date (yyyy-mm-dd):",  #
        "experimenter_name": "Select the name of experimenter:",
        "Rig": "Select the Rig:",
        "attempt": "Enter attempt (starts with 1):",  #
        "Task": "Select the Task:",
        # "force_field:" "Select the Forcefield:",
        "MouseLicensing": "Select the license:",
        "Anesthesia": "Anesthesia",
        "MouseScoreSheet_BodyCondition": "Select the Body Condition:",
        "MouseScoreSheet_GeneralAssay": "General Assay:",
        "MouseScoreSheet_HousingAssesment": "Housing assay:",
        "weight_percentage": "Enter delta % weight:",
        "session_notes": "Session notes:"
        # "surgery_type": "Surgery type"
    }


def _set_exp_choices(dj_dict):
    """
    The type of PyQt element will be deduced based on the presence of the key in current dictionary.

    Args:
       dj_dict (dict): A dictionary with experiment fields and their corresponding values.

    Returns:
       dict: A dictionary containing the choices available for each experiment field.
             The keys are the same as those in `dj_dict`, and the values are lists of
             strings representing the available choices for each field.
    """
    return {
        "experimenter_name": dj_dict['experimenter_name'],
        "Rig": dj_dict['Rig'],
        "Task": dj_dict['Task'],
        "task_type": dj_dict['task_type'],
        # "force_field:" dj_dict['ForceField'],
        "MouseLicensing": dj_dict['MouseLicensing'],  # different name
        "Anesthesia": dj_dict['Anesthesia'],
        "MouseScoreSheet_BodyCondition": dj_dict['MouseScoreSheet_BodyCondition'],
        "MouseScoreSheet_GeneralAssay": dj_dict['MouseScoreSheet_GeneralAssay'],
        "MouseScoreSheet_HousingAssesment": dj_dict['MouseScoreSheet_HousingAssesment'],
        # "surgery_type": dj_dict['surgery_type']
    }


def _set_primary_keys():
    """
    Set primary keys for different tables in the database.

    Returns:
        A dictionary where keys are table names and
        values are the name of the primary key for that table.
    """
    return {
        "Rig": "rig_id",
        "Task": "task_name",
        # "ForceField": "force_field_name",
        "MouseLicensing": "license",
        "Anesthesia": "anesthesia_name",
        "MouseScoreSheet_BodyCondition": "body_condition",
        "MouseScoreSheet_GeneralAssay": "general_assay",
        "MouseScoreSheet_HousingAssesment": "housing_assay",
    }


class Exp(Template):
    """
    Class representing an Experiment GUI object.
    """

    def __init__(self, dj_dict, widget):
        """
        Initializes an Experiment object.

        Args:
           dj_dict: Dictionary with DataJoint tables and their corresponding rows.
           widget: QWidget object containing the GUI.
        """
        super().__init__(widget=widget, nick="exp",
                         labels=_set_exp_labels(), choices=_set_exp_choices(dj_dict),
                         primary_keys=_set_primary_keys())

        self.special_fields = {
            "doe": self._doe,
            "session_notes": self._session_notes,
            "weight_percentage": self._weight,
        }

    def _experiment_details(self, dj_dict, json_dict, date):
        """
        Adds the experiment details section to the GUI.

        Args:
           dj_dict: Dictionary with DataJoint tables and their corresponding rows.
           json_dict: Dictionary with experiment details.
           date: Date of the experiment.
        """
        section_name = 'EXPERIMENT DETAILS'
        label = QLabel(section_name)
        self.main_layout.addWidget(label)  # , alignment=Qt.AlignCenter)
        label.setStyleSheet("font-weight: bold")

        layout = QGridLayout()
        self.main_layout.addLayout(layout)

        labels = self.get_labels()

        i = 0  # grid raw coordinate
        j = 0  # grid column coordinate

        for key, value in labels.items():

            if key in self.special_fields.keys():
                i += 1
                self._create_special_field(key=key, labels=labels, layout=layout,
                                           i=i, date=date)
            else:
                label = QLabel(labels[key])
                layout.addWidget(label, i, j, alignment=Qt.AlignLeft)
                # todo general "no option"
                choices = self.get_choices()
                if key in choices.keys():  # combobox
                    choices = self._filter_choices(choices, key)
                    self._create_combobox(key, choices, layout, json_dict, i, j)
                else:
                    self._create_input_field(key, layout, i, j)

                    # todo special fileds
                    if key == "attempt":  # TODO check and init
                        self.values[key].setText("1")

            i, j = get_idx(i, j, self.max, step=2)
            self.main_layout.addStretch()

    def _filter_choices(self, choices, key, restriction="task_type"):
        """
        Filters choices based on a given key and restriction.

        Args:
           choices: Dictionary with experiment choices.
           key: Key of the field being filtered.
           restriction: Key of the field to which the filter should be applied.

        Returns:
           Dictionary with the filtered choices.
        """
        if key == "Task":
            if restriction in self.choices.keys():
                type = self.get_choices(restriction)[0]
                ret = list()
                idx = 0
                delete = list()
                for choice in choices[key]:
                    if choice["task_name"] != str(type):
                        delete.append(choice)
                    idx += 1
                for d in delete:
                    choices[key].remove(d)

        if key == "Rig":    #todo general
            choices[key] = [choices[key][11]]
        return choices

    def _doe(self, key, date, **kwargs):
        """
        Sets the date of the experiment.

        Args:
          key: Key of the experiment detail.
          date: Date of the experiment.

        Returns:
          True if the date was set successfully, False otherwise.
        """
        self.values[key] = QLabel(date)
        return True

    def _session_notes(self, key, label, **kwargs):  # todo(mary) generate: + surgery
        """
        Create session notes layout.

        Args:
           key (str): The key to be used to store the notes.
           label (QLabel): The label for the session notes.
           **kwargs: Additional keyword arguments.

        """
        label.setStyleSheet("font-weight: bold")
        layout_notes = QVBoxLayout()

        self.no_value[key] = QCheckBox(self.widget)
        self.no_value[key].setText("no notes")
        layout_notes.addWidget(self.no_value[key])

        self.values[key] = QPlainTextEdit(self.widget)
        layout_notes.addWidget(self.values[key])
        self.main_layout.addLayout(layout_notes)

    def _weight(self, key, date, **kwargs):
        """
        Sets the weight of mouse during the current session.

        Args:
           key (str): The key to use for storing the weight information.
           date (str): The date of the experiment.
           **kwargs: Additional keyword arguments.

        Returns:
           bool: True if the weight is set, False otherwise.
        """
        self.values[key] = QLineEdit()
        self.values[key].setFixedWidth(int(get_min_len()))
        self.no_value[key] = QCheckBox(self.widget)
        self.no_value[key].setText("no weight info")
        self.info["doc"] = date
        return True

    def update_date(self, date, key="doe"):
        """
         Updates the date of an experiment.

         Args:
             date (str): The new date of the experiment.
             key (str): The key to use for storing the date of the experiment. Default is "doe".

         Returns:
             bool: True if the date is updated, False otherwise.
         """
        curr_date = self.values[key].text()
        if curr_date != date:
            msg = "Date of experiment will be updated according to selected file."
            dlg = AlertMsg(self.widget, msg, cancel=True)
            ret = dlg.exec()
            if ret == 0:
                return False
            self.values[key].setText(date)
        return True

    def update_attempt(self, attempt, key="attempt"):
        """
        Updates the attempt value for the given key.

          Args:
              attempt (str): The new attempt value.
              key (str, optional): The key to update. Defaults to "attempt".

          Returns:
              bool: True if the attempt was updated, False otherwise.
          """
        curr_attempt = self.values[key].text()
        if curr_attempt != attempt:
            msg = "Attempt will be updated according to selected file."
            dlg = AlertMsg(self.widget, msg, cancel=True)
            ret = dlg.exec()
            if ret == 0:
                return False
            self.values[key].setText(attempt)
        return True

    def run(self, dj_dict, json_dict, date):
        """
        Wrapper to keep the unique interface to class entry point
        """
        self._experiment_details(dj_dict, json_dict, date)

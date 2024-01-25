from PyQt5.QtWidgets import QLabel, QGridLayout, QComboBox, \
    QVBoxLayout, QCheckBox, QPlainTextEdit, QLineEdit, QPushButton
from PyQt5.QtCore import Qt
from utils.helpers import get_idx
from modules.template import Template

"""
    Script contains the optogenetics related GUI module 
"""


def _set_opto_labels():
    """
        Creates a dictionary of labels to be used as prompts for user input during an experiment setup.

        Returns:
            dict: A dictionary containing labels for user prompts.
    """
    return {
        # 'new_optogenetics_entry': "Add new entry", # if new entry, the following fields are needed:
        # 'no_opto': 'No optogenetics:',
        'opto_name': "Optogenetics:",
        'OptogeneticsVariant': "Optogenetics Variant:",
        'OptogeneticsTiming': "Optogenetics Timing:",
        'OptogeneticsRegion': "Optogenetics Region:",

        # 'pulse_frequency': "Pulse Frequency(Hz):",
        # 'laser_power': "Laser Power(mW):",
        # 'pulse_length': "Pulse Length(ms):",
    }


def _set_opto_choices(dj_dict):
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
        # opotgenetics
        'opto_name': dj_dict['opto_name'],
        # if new entry, the following fields are needed:
        'OptogeneticsVariant': dj_dict['OptogeneticsVariant'],
        'OptogeneticsTiming': dj_dict['OptogeneticsTiming'],
        'OptogeneticsRegion': dj_dict['OptogeneticsRegion'],
    }


def _set_primary_keys():
    """
        Set primary keys for different tables in the database.

        Returns:
            A dictionary where keys are table names and
            values are the name of the primary key for that table.
    """
    return {
        "OptogeneticsVariant": "opto_variant_name",
        "OptogeneticsTiming": "opto_timing_name",
        "OptogeneticsRegion": "opto_region_name",
    }


class Opto(Template):
    """
    A class representing an Optogenetics and implementing Template abstract class.

    Attributes:
        widget (QWidget object): represents the main widget for the template.
        nick (str): represents a shortened name for the template.
        labels (dict): A dictionary containing the labels for the fields in the template.
        choices (dict): A dictionary containing the choices for the fields in the template.
        primary_keys (dict): A dictionary containing the primary keys for the fields in the template.
        special_fields (dict): A dictionary containing the special fields for the template.

    Methods:
        init(self, dj_dict, widget): Initializes the Opto object.
        _optogenetics_details(self, dj_dict, json_dict, **kwargs):
            Adds the optogenetics details section to the main_layout.
        _selected_opto_callback(self, evt=None):
            A callback function to handle selected optogenetics.
        _add_new_opto(self, key): A function to add a new optogenetics entry.
        _create_button(self, key): A function to create a button.
        _deactivate_button(self, key): A function to deactivate a button.
        _activated(self, evt, main_key): A callback function to activate a button.
        _deactivated(self, evt, main_key): A callback function to deactivate a button.
        run(self, dj_dict, json_dict, date): A function to run the Opto template.
    """

    def __init__(self, dj_dict, widget):
        super().__init__(widget=widget, nick="opto",
                         labels=_set_opto_labels(), choices=_set_opto_choices(dj_dict),
                         primary_keys=_set_primary_keys())

        self.special_fields = {
            # "new_optogenetics_entry": self._add_new_opto,
            # "no_opto": self._no_opto,
        }

    def _optogenetics_details(self, dj_dict, json_dict, **kwargs):
        """
            Populate the layout with the optogenetics details section.

            Args:
                dj_dict (dict): A dictionary containing information from the DataJoint table.
                json_dict (dict): A dictionary containing information from the JSON file.
                **kwargs: Optional keyword arguments.

            The method creates and adds widgets to the layout to display the optogenetics details section of the form.
            The section includes a QLabel with the text "OPTOGENETICS DETAILS",
            followed by input fields and/or comboboxes
            to allow the user to enter or select the corresponding values.
            The method also defines the callbacks for the optogenetics name combobox and the "none" checkbox.

            If a key in the 'special_fields' dictionary is encountered, the method will call the '_create_special_field'
            method to create a specific type of input field.

            The 'labels' and 'choices' dictionaries are obtained from the parent class 'Template'.
            The input fields and comboboxes are created and added to the 'layout' using methods '_create_input_field'
            and '_create_combobox' respectively.

            Finally, the method calls the '_selected_opto_callback' to set the default values in the fields based on
            the value selected in the 'opto_name' combobox.
            """

        section_name = 'OPTOGENETICS DETAILS'
        label = QLabel(section_name)
        self.main_layout.addWidget(label)  # , alignment=Qt.AlignCenter)
        label.setStyleSheet("font-weight: bold")

        layout = QGridLayout()
        self.main_layout.addLayout(layout)

        labels = self.get_labels()
        # grid coordinates
        i = 0
        j = 0

        for key, value in labels.items():

            if key in self.special_fields.keys():
                i += 1
                self._create_special_field(key=key, labels=labels, layout=layout, i=i, j=0)
            else:
                label = QLabel(labels[key])
                layout.addWidget(label, i, j, alignment=Qt.AlignLeft)

                choices = self.get_choices()
                if key in choices.keys():  # combobox
                    self._create_combobox(key, choices, layout, json_dict, i, j)
                    if key == "opto_name":
                        self.values[key].activated[str].connect(
                            lambda evt: self._selected_opto_callback(evt))
                else:
                    self._create_input_field(key, layout, i, j)

            i, j = get_idx(i, j, self.max, step=2)
            self.main_layout.addStretch()
            self._selected_opto_callback()

    def _selected_opto_callback(self, evt=None):
        """
            Callback method to handle selection of optogenetics name from combobox.

          Args:
              evt (QEvent, optional): The event that triggered the callback. Defaults to None.

            Sets the values of all other combo boxes to "-" if 'opto_name' is set to a non-'None' value,
            or to the first item containing 'None' if 'opto_name' is set to 'None'.
        """
        value = self.values["opto_name"].currentText()

        if value.lower() == "none":
            for key, value in self.values.items():
                all_items = [self.values[key].itemText(i) for i in range(self.values[key].count())]
                for item in all_items:
                    arr = item.split("-")
                    if "none" in arr[0].lower():
                        self.values[key].setCurrentText(item)
        else:
            for key, value in self.values.items():
                if key != "opto_name":
                    self.values[key].setCurrentText("-")

    def _add_new_opto(self, key):
        """
           Adds a button to the widget to add new opto entry.

           Args:
               key (str): The unique identifier for the new opto button.

           Returns:
               bool: True if the new opto button was successfully added, False otherwise.
           """
        self.values[key] = self._create_button(key)
        return True

    def _create_button(self, key):
        """
          Creates a new QPushButton with the specified label and
          connects it to the widget's `_activated` method.

          Args:
              key (str): The unique identifier for the new QPushButton.

          Returns:
              QPushButton: The newly created QPushButton.
          """
        button = QPushButton(self.labels[key])
        button.clicked.connect(
            lambda evt, args=key: self._activated(evt, key))
        return button

    def _deactivate_button(self, key):
        """
         Deactivates a QPushButton by changing its label and
         connecting it to the widget's `_deactivated` method.

         Args:
             key (str): The unique identifier of the QPushButton to be deactivated.
         """
        self.values[key].setText("Submit " + self.labels[key])
        self.values[key].clicked.connect(
            lambda evt, args=key: self._deactivated(evt, key))

    def _activated(self, evt, main_key):
        """
           Deactivates a QPushButton by changing its label and
           connecting it to the widget's `_deactivated` method.

           Args:
               key (str): The unique identifier of the QPushButton to be deactivated.
        """
        for key, value in self.labels.items():
            if key in self.choices.keys():
                item = QLineEdit(self.widget)
                self.values[key].setLineEdit(item)
        self._deactivate_button(main_key)

    def _deactivated(self, evt, main_key):
        """
            This method is called when a field "Add new" is deactivated.
            It restores the field to its default label and disables the edit
            mode of the dropdown list.

            Args:
            - evt: PyQt event object
            - main_key: the main key of the field which is deactivated
        """
        self.values[main_key].setText(self.labels[main_key])
        for key, value in self.labels.items():
            if key in self.choices.keys():
                item = self.values[key].currentText()
                self.values[key].addItem(item)
                self.values[key].setCurrentText(item)
                self.values[key].setEditable(False)
        self.values[main_key].clicked.connect(
            lambda evt, args=key: self._activated(evt, main_key))

    def run(self, dj_dict, json_dict, date):
        """
           Runs the optogenetics details widget with the specified data.

           Args:
               dj_dict (dict): A dictionary containing the data  from datajoint database.
               json_dict (dict): A dictionary containing the cache data from .json file.
               date (str): The date of the current experiment.
        """
        self._optogenetics_details(dj_dict, json_dict)

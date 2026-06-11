from abc import ABC, abstractmethod

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QComboBox, QLabel, QLineEdit

from utils.helpers import get_min_len, get_size
from utils.utils import get_options


"""
    Script contains the template for all GUI's modules
    Abstract class to inherit!
"""


class Template(ABC):
    """
    This class represents a template for creating modules of GUI interface (mice, exp, opto...).
    It is an abstract class and is meant to be inherited by
    other classes to create specific templates.

    Methods:

        init(self, widget, nick, labels, choices=None, primary_keys=None): Constructor method for the Template class.
        get_nick(self): Returns the nick name of the template.
        get_labels(self, key=None): Returns the label(s) associated with a given key,
                                    or all labels if no key is given.
        get_choices(self, key=None): Returns the choices associated with a given key,
                                    or all choices if no key is given.
        get_info(self, key=None): Returns the information associated with a given key,
                                    or all information if no key is given.
        get_values(self): Returns a dictionary containing all the values.
        get_primary_keys(self, key=None): Returns the primary key(s) associated with a given key,
                                    or all primary keys if no key is given.
        get_key2info(self, key=None): Returns the key2info dictionary associated with a given key,
                                    or the entire key2info dictionary if no key is given.
        _create_special_field(self, key, labels, layout, i, j=0, date=None): Creates a special field for a given key.
        _create_combobox(self, key, choices, layout, json_dict, i, j): Creates a combobox for a given key.
        _create_input_field(self, key, layout, i, j): Creates an input field for a given key.
        empty_check(self): Checks if any of the fields have been left empty.
        run(self, **args): Abstract method that must be implemented by the child class.
                            It is meant to perform a specific action when the template is run.
    """

    @abstractmethod
    def __init__(self, widget, nick, labels, choices=None, primary_keys=None):

        self.widget = widget
        self.main_layout = self.widget.main_layout

        self.nick = nick
        self.labels = labels
        self.choices = choices

        self.primary_keys = primary_keys
        self.key2info = dict()

        self.values = dict()
        self.info = dict()

        self.max = 3

        self.no_value = dict()
        self.special_fields = None

    def get_nick(self):
        return self.nick

    def get_labels(self, key=None):
        if key is not None:
            return self.labels[key]

        return self.labels

    def get_choices(self, key=None):
        if key is not None:
            return self.choices[key]
        return self.choices

    def get_info(self, key=None):
        if key is not None:
            return self.info[key]
        return self.info

    def get_values(self):
        return self.values

    def get_primary_keys(self, key=None):
        if key is not None:
            return self.primary_keys[key]
        return self.primary_keys

    def get_key2info(self, key=None):
        if key is not None:
            return self.key2info[key]
        return self.key2info

    def _create_special_field(self, key, labels, layout, i, j=0, date=None):
        """
        Create a special field in the UI layout based on the given key.

        Args:
            key: A string representing the key of the field to be created.
            labels: A dictionary containing label names for each field.
            layout: A QGridLayout representing the layout of the UI.
            i: An integer representing the row of the layout where the field should be added.
            j: An integer representing the column of the layout where the field should be added.
            date: A QDate object representing the date associated with the field (if any).
        """
        label = QLabel(labels[key])
        layout.addWidget(label, i, j, alignment=Qt.AlignLeft)

        if self.special_fields[key](key=key, date=date, label=label):
            layout.addWidget(self.values[key], i, j + 1, alignment=Qt.AlignLeft)

            if key in self.no_value.keys():
                layout.addWidget(self.no_value[key], i, j + 2, alignment=Qt.AlignLeft)

    def _create_combobox(self, key, choices, layout, json_dict, i, j):
        """
        Creates a QComboBox widget with specified choices and layout and adds it to the current widget.

        Args:
            key (str): The key associated with the QComboBox.
            choices (list): The list of choices to display in the QComboBox.
            layout (QGridLayout): The QGridLayout object to add the QComboBox to.
            json_dict (dict): The dictionary object containing key-value pairs of JSON data.
            i (int): The row index in the layout to add the QComboBox to.
            j (int): The column index in the layout to add the QComboBox to.

        Notes:
        - This method sets the fixed width of the QComboBox based on the length of the options.
        - If the key is in json_dict,
            the method sets the current text of the QComboBox to the value in the dictionary.
        - If the key is in the primary_keys and the associated primary key is in json_dict,
            the method sets the current text of the QComboBox to the corresponding option.
        """
        self.values[key] = QComboBox(self.widget)

        options = get_options(choices, key, self.key2info, self.primary_keys)
        len_elm = get_size(options)  # adjust size of graphical element

        self.values[key].setFixedWidth(int(len_elm))
        layout.addWidget(self.values[key], i, j + 1, alignment=Qt.AlignLeft)
        self.values[key].addItems(options)

        if key in json_dict.keys():
            self.values[key].setCurrentText(json_dict[key])

        elif key in self.primary_keys.keys():
            if self.primary_keys[key] in json_dict.keys():
                val = str(json_dict[self.primary_keys[key]])
                for elm in options:
                    if val in elm:
                        val = elm
                        break
                self.values[key].setCurrentText(val)

    def _create_input_field(self, key, layout, i, j):
        """
        Creates a QLineEdit input field and adds it to the specified QGridLayout object
        at the specified row and column indices.

        Args:
            key (str): The key associated with the QLineEdit input field.
            layout (QGridLayout): The QGridLayout object to add the QLineEdit input field to.
            i (int): The row index in the layout to add the QLineEdit input field to.
            j (int): The column index in the layout to add the QLineEdit input field to.

        Notes:
        - This method sets the fixed width
        of the QLineEdit input field based on the minimum length required for the input.
        - The QLineEdit input field is stored in the values dictionary with the specified key.
        """

        self.values[key] = QLineEdit()
        self.values[key].setFixedWidth(int(get_min_len()))
        layout.addWidget(self.values[key], i, j + 1, alignment=Qt.AlignLeft)

    def empty_check(self):
        """
        Updates the 'info' dictionary with the value "none"
        for any keys that correspond to QCheckBox objects that are currently checked.

        Notes:
        - This method iterates over the 'no_value' dictionary, which maps keys to QCheckBox objects.
        - If a QCheckBox object is checked, the corresponding key in the 'info' dictionary is set to "none".
        """
        for key, value in self.no_value.items():
            if value.isChecked():
                self.info[key] = "none"

    def run(self, **args):
        """
        The method that combines all class methods to be called in main
        """
        pass

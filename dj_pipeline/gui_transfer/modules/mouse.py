import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QComboBox, QGridLayout, QLabel, QVBoxLayout

from modules.template import Template
from utils.alert import AlertMsg
from utils.helpers import get_idx, get_size, get_step


"""
    Script contains the mouse related GUI module 
"""


def _set_mice_labels():
    """
    Creates a dictionary of labels to be used as prompts for user input during an experiment setup.

    Returns:
        dict: A dictionary containing labels for user prompts.
    """
    return {
        "mouse_name": "Select mouse name:",
        "start_date": "First experiment date (yyyy-mm-dd):",
        "day": "Current day of the mouse:",
        "mouse_id": "Mouse ID:",
        "dob": "Date of birth (yyyy-mm-dd):",
        "sex": "Sex of the mouse:",
        "last_exp": "Last experiment (yyyy-mm-dd):",
        "strain": "Mouse strain:",
    }


class Mouse(Template):
    """
    Represents a mouse-related GUI part.

    Args:
        widget (QWidget): The parent widget for the template.

    Attributes:
        info (dict): Dictionary containing information about the mouse.
        auto_mouse (bool): Flag indicating if the mouse is authorized to be updated
                             automatically or not (ex. when new file is selected)

    Methods:
        set_mouse_info(mouse_dict, name=None):
            Set the mouse information using a mouse dictionary and optional name.
        _mouse_details(dj_dict, json_dict, **kwargs):
            Selects a mouse in the combo box and initializes the GUI's form with labels to show the mouse information.
        _selected_mouse_callback(event, dj_dict):
            Fill the information buffer dictionary with selected mouse information.
        update_mouse(mouse, dj_dict):
            Updates the mouse name according to the selected file.
        set_auto(val):
            Set the auto_mouse attribute to True or False.
        get_auto():
            Returns the value of the auto_mouse attribute.
        run(dj_dict, json_dict, date):
            Runs the mouse details display.

    """

    def __init__(self, widget):

        super().__init__(widget=widget, nick="mouse", labels=_set_mice_labels())
        self.auto_mouse = True

    def set_mouse_info(self, mouse_dict, name=None):
        """
        Set information about a mouse.

        Args:
            mouse_dict (dict): A dictionary containing information about the mouse. The dictionary must
                have the following keys: 'start_date' (str), 'day' (str), 'mouse_id' (str), 'dob' (str),
                'sex' (str), 'last_exp' (str), and 'strain' (str). The values associated with these
                keys provide information about the mouse, and are used to populate the attributes of
                the 'info' dictionary.
            name (str, optional): The name of the mouse. Defaults to None.

        Raises:
            TypeError: If 'mouse_dict' is not a dictionary or if it does not have all of the required
                keys.
        """
        self.info = {
            "mouse_name": name,  # mouse
            "start_date": mouse_dict["start_date"],  # inter
            "day": mouse_dict["day"],  # ? session
            "mouse_id": mouse_dict["mouse_id"],  # mouse
            "dob": mouse_dict["dob"],  # mouse
            "sex": mouse_dict["sex"],  # mouse
            "last_exp": mouse_dict["last_exp"],  # inter
            "strain": mouse_dict["strain"],  # mouse/strain
        }

    def _mouse_details(self, dj_dict, json_dict, **kwargs):
        """
        Function to select a mouse from a dropdown menu and display information about the mouse.

        The function pre-initializes the GUI's form with labels that will later show information about the selected mouse.
        For default values, the function uses data from a JSON cache.

        Args:
            dj_dict (dict): A dictionary containing information about the mouse menu.
            json_dict (dict): A dictionary containing cached information in JSON format.
            **kwargs: Additional keyword arguments.
        """
        section_name = "MOUSE DETAILS"
        label = QLabel(section_name)
        self.main_layout.addWidget(label)  # , alignment=Qt.AlignCenter)
        label.setStyleSheet("font-weight: bold")

        layout = QGridLayout()  # local layor locl grid
        self.main_layout.addLayout(layout)

        # self.setStyleSheet('background: black; color: white')

        self.values = dict()
        labels = self.get_labels()

        # grid coordinates
        i = 0
        j = 0
        l = len(labels.items())
        max_col = (l / 2 - 1) * get_step()
        if max_col >= 4:
            max_col = self.max

        for key, value in labels.items():
            layout.addWidget(QLabel(labels[key]), i, j, alignment=Qt.AlignLeft)

            if key == "mouse_name":
                self.values[key] = QComboBox(self.widget)
                options = ["-"] + list(
                    dj_dict["MouseDict"]
                )  # list = unpack (get keys aka names)
                len_elm = get_size(options)
                self.values[key].setFixedWidth(int(len_elm))

                layout.addWidget(self.values[key], i, j + 1, alignment=Qt.AlignLeft)
                self.values[key].addItems(options)
                self.values[key].activated[str].connect(
                    lambda evt, temp=dj_dict: self._selected_mouse_callback(evt, temp)
                )
                if key in json_dict.keys():
                    self.values[key].setCurrentText(json_dict[key])

            else:
                self.values[key] = QLabel("")
                layout.addWidget(self.values[key], i, j + 1)

            i, j = get_idx(i, j, max_col, step=2)

        self.main_layout.addStretch()
        self._selected_mouse_callback(None, dj_dict)

    def _selected_mouse_callback(self, event, dj_dict):
        """
        Function to fill the information from selected mouse to the buffer info dictionary
        Args:
            name(str): mouse name
            dj_dict(dict): menu dictionary
        """
        # finding the content of current item in combo box
        name = self.values["mouse_name"].currentText()

        if name in dj_dict["MouseDict"].keys():
            mouse_dict = dj_dict["MouseDict"][name]
        else:
            return False

        self.set_mouse_info(mouse_dict, name)

        for key, value in self.values.items():
            if key != "mouse_name":
                self.values[key].setText(str(self.get_info(key)))

    def update_mouse(self, mouse, dj_dict):
        """
        Updates the mouse information if the selected file's mouse name is different from the current mouse name.
        Args:
          mouse (str): Current mouse name.
          dj_dict (dict): Dictionary with data fetched from the database.

        Returns:
          bool: True if the mouse was updated successfully, False otherwise.
        """
        name = self.values["mouse_name"].currentText()
        if name != mouse:
            msg = "Mouse name will be updated according to selected file."
            dlg = AlertMsg(self.widget, msg, cancel=True)
            ret = dlg.exec()
            if ret == 1:
                # update mouse
                options = list(dj_dict["MouseDict"])
                tmp = [x.lower() for x in options]
                if mouse.lower() not in tmp:
                    msg = "Mouse " + mouse + " doesn't exist in the database!"
                    AlertMsg(self.widget, msg).exec()
                    return False
                for x in options:
                    if x.lower() == mouse.lower():
                        mouse = x
                        break
                self.values["mouse_name"].setCurrentText(mouse)
                self._selected_mouse_callback(None, dj_dict)
                return True

            return False
        return True

    def set_auto(self, val):
        """
        Set the value of the `auto_mouse` attribute.
        """
        self.auto_mouse = val

    def get_auto(self):
        """
        Get the value of the `auto_mouse` attribute.
        """
        return self.auto_mouse

    def run(self, dj_dict, json_dict, date):
        """
        Wrapper to keep the unique interface to class entry point
        """
        self._mouse_details(dj_dict, json_dict)

from PyQt5.QtWidgets import QLabel, QGridLayout, QTextEdit, QPushButton, QFileDialog

from utils.helpers import get_max, get_pattern
from modules.template import Template
from utils.utils import check_files
from config.config import config, logger

from pathlib import Path
import os
from moviepy.editor import VideoFileClip


def get_type(filename):
    """
    Determines the type of given file based on its filename and returns associated key.

    Args:
       filename (str): The name of the file.

    Returns:
       str: A string representing the type of the file. The possible values are:
           - "video_path": If the filename contains "VIDEO".
           - "camera_path": If the file contians "TS" (timestamps from camera gui)
           - "dlc_path": If the file is a DLC model file
           - "proc_path": If the file is a processed data file (contains "PROC")
           - "teensy_path": If the file is not any of the above types, returns "teensy_path"
           (as it's the ony one file that hasn't keyword)
    """
    types = {
        "video_path": "VIDEO",  # get video type, duration
        "camera_path": "TS",
        "dlc_path": "DLC",  # precise type : model name
        "proc_path": "PROC",
    }

    for key, value in types.items():
        if value in filename:
            return key
    return "teensy_path"  # todo general


def _set_path_format():
    """
    Returns a dictionary containing the file path formats for different types of files.

    Returns:
      dict: A dictionary where each key represents a file type and its value is a string or a list of strings
      specifying the expected file path format(s) for that type.
    """
    return {
        "teensy_path": "*_*_?.pickle",
        "video_path": ["*_*_*_*.avi", "*_*_*_*_VIDEO.*"],  # get video type, duration
        "camera_path": ["TIMESTAMP_*_*_*.npy", "TS_*_*_*.npy", "*_*_*_TS.npy"],
        "dlc_path": [
            "*DLC*.h5",
            "*DLC*_meta.pickle",
            "*_*_*_*_DLC.hdf5",
        ],  # precise type : model name
        "proc_path": ["*PROC"],
    }


def _set_labels():
    """
    Creates a dictionary of labels to be used as prompts for user input during an experiment setup.

    Returns:
        dict: A dictionary containing labels for user prompts.
    """
    return {
        "teensy_path": "teensy",
        "dlc_path": "dlc",  # todo add model name, add proc
        "camera_path": "camera",  # ts
        "video_path": "video",
        "proc_path": "proc",
        # "self_path" todo
    }


def _path_is_remote(key):  # todo better
    """
    Determines whether the specified file type is expected to have a remote path or not.
    Currently, it's the case only of video_path-typed file

    Args:
      key (str): The file type (key) to check.

    Returns:
      bool: True if the file type is expected to have a remote path, False otherwise.
    """
    if key == "video_path":
        return True
    return False


def get_dst_folder(key):  # todo config
    """
    Determines the name of destination folder for every file type.
    (used to define the destination remote directory for file transfer)

    Args:
      key (str): The file type to check.

    Returns:
      str: The destination folder for the specified file type.
       If the file type is not teensy_path or gui_output, dlc_video is returned.
    """
    if key == "teensy_path" or key == "gui_output":
        return "data"
    return "dlc_video"


class Transfer(Template):
    """
    Class to handle file transfer.
    """

    def __init__(self, widget, keys=None):
        """
        Initialize Transfer class.

        Args:
           widget (QWidget): QWidget that the class is running on (main widget)
           keys (list, optional): List of keys to use.
                    Defaults to None that corresponds to the use of all defined keys.
        """
        super().__init__(widget=widget, nick="transfer", labels=_set_labels())

        self.files_labels = dict()
        self.transfer_file = dict()

        self.path_format = _set_path_format()
        self.cache_paths = dict()

        if keys is None:
            self.keys = _set_labels().keys()
        else:
            self.keys = keys

    def get_nick(self):
        """
        Get the nick name.
        Returns:
           str: The nick name.
        """
        return self.nick

    def get_format(self, key=None):
        """
        Get the path format for the specified key.

        Args:
           key (str, optional): The key to get the path format for.

        Returns:
           dict or str: The path format for the specified key, or all path formats (if key is None)
        """
        if key is not None and key in self.get_keys():
            return self.path_format[key]
        return self.path_format

    def get_labels(self, key=None):  # todo check miss
        """
        Get the label(s) for the specified key.

        Args:
            key (str, optional): The key to get the label(s) for.

        Returns:
            list or str: The label(s) for the specified key, or all labels (if key is None)
        """
        if key is not None and key in self.get_keys():
            return self.labels[key]
        return self.labels.values()

    def get_keys(self):
        """
        Get the keys.

        Returns:
          list: The keys.
        """
        return self.keys

    def get_info(self):
        """
        Get the transfer files and the info: all data that will be added in .npy output file.

        Returns:
            dict: The transfer files and the info.
        """
        return {**self.transfer_file, **self.info}

    def get_transfer_files(self, key=None, send=False):
        """
        Get all the files that should be transferred (if send true), or just all known files from transfer dictionary.

        Args:
          key (str, optional): The key to get the transfer file for. Defaults to None.
          send (bool, optional): Whether to only return files that are not remote. Defaults to False.

        Returns:
          dict or None: The transfer file for the specified key, or all transfer files.
        """
        if key is not None and key in self.get_keys():
            return self.transfer_file[key]

        if send is True:
            ret = dict()
            for k, f in self.transfer_file.items():
                if not _path_is_remote(k):
                    ret[k] = f
            return ret

        return self.transfer_file

    def get_processed_files(self):
        """
        Get the processed files.

        Returns:
          list: The processed files.
        """
        args = ["gui_output", "teensy_path"]
        ret = list()
        for a in args:
            ret.append(self.get_transfer_files(key=a))
        return ret

    def get_cache_paths(self):
        """
        Get the cache paths.

        Returns:
            dict: The cache paths.
        """
        return self.cache_paths

    def _transfer_buttons(self, dj_dict, args):
        """
        Create buttons for file transfer.

        Args:
            dj_dict (dict): The datajoint dictionary.
            args (dict): The arguments dictionary
                        that contains links to other fields of gui, to have access to mouse/exp/opto
        """
        section_name = "FILES FOR TRANSFER"
        label = QLabel(section_name)
        self.main_layout.addWidget(label)
        label.setStyleSheet("font-weight: bold")

        layout = QGridLayout()
        self.main_layout.addLayout(layout)
        i = 0
        j = 0
        len_elm = (get_max(self.get_labels()) + 10) * 10

        for key in self.keys:
            self.transfer_file[key] = None

            # no_file = QCheckBox(self)
            # no_file.setText("no file")
            # layout.addWidget(no_file, i, j) #todo(mary)

            msg = "Add " + self.get_labels(key) + " file"
            file_browse = QPushButton(msg)
            file_browse.setFixedWidth(len_elm)

            file_browse.clicked.connect(
                lambda evt, key=key, args=args: self._open_file_dialog(
                    evt, key, dj_dict, args
                )
            )

            layout.addWidget(file_browse, i, j)
            self.files_labels[key] = QTextEdit("")  # QLabel("")
            self.files_labels[key].setReadOnly(True)
            # self.files_labels[key].setFixedWidth(1000)
            layout.addWidget(self.files_labels[key], i, j + 1)

            i += 1

        self.main_layout.addStretch()

    def _open_file_dialog(self, evt, key, dj_dict, args):
        """
        Opens a file dialog to select one or multiple image files and updates the GUI accordingly.

        Args:
          evt: The event that triggered the file dialog.
          key (str): The key of the file selector widget.
          dj_dict: A dictionary of parameters for the data joint pipeline.
          args (dict): A dictionary of arguments including the mouse and experiment parameters.

        Returns:
          bool: False if the file selection is invalid, True otherwise.

        Note:
            according to selected file it updates mouse and exp fields, predicts other files to upload
        """
        mouse = args["mouse"]
        exp = args["exp"]
        # cache = args["cache"]
        # todo: check key miss

        format = self.get_format(key)
        multiple_on = False

        if (
            multiple_on and key == "dlc_path"
        ):  # todo automatically for certain cases/pre-selection
            filenames, _ = QFileDialog.getOpenFileNames(
                self.widget,
                "Select Files",
                config.get_path(key),
                "Images (" + get_pattern(key, format) + ")",
            )
        else:
            filenames, _ = QFileDialog.getOpenFileName(
                self.widget,
                "Select Files",
                config.get_path(key),  # where
                "Images (" + get_pattern(key, format) + ")",
            )

        if filenames is not None and len(filenames) > 0:
            mice_part = mouse.values != dict()

            if mice_part:  # mouse was already setted   #TODO for all cases re-new
                current_mouse = mouse.values["mouse_name"].currentText()

            ret = check_files(key, filenames, self.get_format(key))  # todo adjust

            if isinstance(ret, bool) and ret is False:  # update
                return False

            if isinstance(ret, tuple):  # update data in gui according to file
                _mouse, _attempt, _date = ret

                if (
                    mice_part
                    and mouse.update_mouse(_mouse, dj_dict)
                    and mouse.get_auto()
                ):
                    # mouse.set_auto(False) # once?
                    exp.update_date(_date)
                    exp.update_attempt(_attempt)

            # att filename can be list
            self._set_file(key, filenames)  # file added
            self._set_cache_paths(key, filenames)  # update cache with parent folder
            self.files_labels[key].setText(str(filenames))  # show selected path on gui

            # predict other files (in the same folder)

            processed_keys = self._pre_fetch_files(filenames)
            processed_keys.append(key)
            self._check_video(processed_keys)

    def _check_video(self, keys, video_label="video_path"):
        """
        Extracting of video's metadata and updates `self.info` dictionary.
        Args:
            keys (List[str]): List of keys to check for video file.
            video_label (str): Key to video file in `self.transfer_file`
        """

        if video_label in keys:
            info_video = self.transfer_file[video_label]
            filename = Path(info_video["src"]).joinpath(info_video["filename"])
            self.info["video_meta"] = dict()
            self.info["video_meta"]["duration"] = 0
            self.info["video_meta"]["fps"] = 0
            self.info["video_meta"]["width"] = 0
            self.info["video_meta"]["height"] = 0

            clip = VideoFileClip(str(filename))
            if clip:
                if clip.duration:
                    self.info["video_meta"]["duration"] = clip.duration
                if clip.fps:
                    self.info["video_meta"]["fps"] = clip.fps
                if clip.size:
                    (
                        self.info["video_meta"]["width"],
                        self.info["video_meta"]["height"],
                    ) = clip.size

                    # todo err

    def _pre_fetch_files(self, filenames):
        """
        Fetches files with same prefix as given filename and adds them to GUI.

        Args:
            filenames (str): Name of file to use for prefix.

        Returns:
            list: List of processed keys.
        """
        # todo for pickle too
        parent = config.get_config("dlc_path")
        filename = Path(filenames).name
        name = filename.split(".")[0]

        paths = os.listdir(parent)

        processed_keys = list()
        for filepath in paths:
            if name in filepath and filename != filepath:
                key = get_type(Path(filepath).name)
                filepath = Path(parent).joinpath(filepath)
                if not filepath.exists():
                    logger.info("ERR: " + str(filepath) + " not found.")
                self._set_file(key, filepath)  # file added
                self._set_cache_paths(key, filepath)  # update cache with parent folder
                self.files_labels[key].setText(
                    str(filepath)
                )  # show selected path on gui
                processed_keys.append(key)
        return processed_keys

    def _set_file(self, key, filename):
        """
        Sets the file path of a given key and updates the transfer file dictionary.

        Args:
        key (str): The key corresponding to the file.
        filename (str): The path of the file.

        """

        dst_folder = config.get_dst_path
        dst = Path(dst_folder).joinpath(get_dst_folder(key))

        self.transfer_file[key] = {
            "filename": str(Path(filename).name),
            "src": str(Path(filename).parent),
            "dst": str(dst),
        }

    def set_npy(self, npy_file):
        """
        Sets the file path of a "gui_output" key and updates the transfer file dictionary.
        """
        self._set_file(key="gui_output", filename=npy_file)

    def _set_cache_paths(self, key, filename):
        """
        Updates the cache paths and the configuration with the parent folder of the given file(s).
        Used to pre-charge files from the folder where they were previously detected.

        Args:
          key (str): The key to use when storing the cache path.
          filename (Union[str, Tuple[str], List[str]]): The filename or list of filenames for which to update the cache path.
        """

        if isinstance(filename, tuple) or isinstance(filename, list):
            filename = filename[0]
        path = str(Path(filename).parent)
        self.cache_paths[key] = path
        config.update(key, path)

    def run(self, dj_dict, args):
        """
        Wrapper to keep the unique interface to class entry point
        """
        self._transfer_buttons(dj_dict, args)

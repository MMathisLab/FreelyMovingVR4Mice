from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from utils.alert import AlertMsg
from utils.logger import Logger
from utils.utils import (
    adjust_keys,
    check_input_video,
    check_missing_data,
    copy_input_videos,
    generate_file,
    get_dataset,
    get_filled_info,
    move_files,
    transfer_files,
)


logger = Logger.get_logger()


"""
    Script contains main GUI widget, and control buttons:
    All GUI's modules (exp, mice) attached to this widget
"""


class Gui(QWidget):
    def __init__(self):
        """
        Class constructor to initialize the GUI's header and layout.

        """
        super().__init__()
        title = "Data Transfer Tool for VR Rig"
        self.setWindowTitle(title)
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.max = 3  # columns in grid
        self.submitted = False

    def _navigation_buttons(self, args):  # , name, info_mouse, info_exp):
        """
        Create and add the Submit and Quit buttons to the GUI.

        Args:
          args (dict): Dictionary containing mouse and experiment info.
        """

        btn_layout = QHBoxLayout()
        self.main_layout.addLayout(btn_layout)

        submit = QPushButton(self)
        submit.setText("Submit")
        submit.clicked.connect(
            lambda evt, args=args: self._submit_callback((evt, args))
        )

        quit = QPushButton(self)
        quit.setText("Quit")
        quit.clicked.connect(self._quit_callback)

        btn_layout.addStretch()
        btn_layout.addWidget(submit)
        btn_layout.addWidget(quit)
        btn_layout.addStretch()

    def _submit_callback(self, args):
        """
        Callback function for the Submit button. Verifies that all information
        has been filled by the user and saves the data to output files.

        Args:
           args (dict): Dictionary containing mouse and experiment info.
        """
        if isinstance(args, tuple):
            args = args[1]

        for key, a in args.items():
            if key != "transfer":
                get_filled_info(info=a.get_info(), values=a.get_values())
                args[key].empty_check()

        if not check_missing_data(self, args):
            return False

        for key, a in args.items():
            if key != "transfer":
                adjust_keys(
                    info=a.get_info(),
                    values=a.get_values(),
                    primary_keys=a.get_primary_keys(),
                    key2info=a.get_key2info(),
                )

        dataset = get_dataset(args["mouse"].get_info(), args["exp"].get_info())
        if not check_input_video(self, args["transfer"], dataset):
            return False

        # generate output files
        npy_file, json_file = generate_file(args)
        if npy_file is None or json_file is None:
            # err msg
            return False

        # add for transfer in dict
        args["transfer"].set_npy(npy_file)

        if not transfer_files(args["transfer"].get_transfer_files(send=True)):
            msg = "Problem during scp transfer!"
            dlg = AlertMsg(self, msg)
            dlg.exec()
            return False

        ok, error = copy_input_videos(args["transfer"].get_input_video_files())
        if not ok:
            logger.warning(f"Input video copy failed: {error}")
            msg = (
                "Data was sent to the server, but the input video copy to the "
                f"Synology failed:\n{error}\nFix it and submit again."
            )
            dlg = AlertMsg(self, msg)
            dlg.exec()
            return False

        try:
            move_files(args["transfer"].get_processed_files())
        except Exception as e:
            logger.warning(f"Could not move files to processed folder: {e}")

        self.submitted = True
        args["mouse"].set_auto(True)
        msg = "All data was submitted and transferred :-) !"
        dlg = AlertMsg(self, msg)
        dlg.exec()

    def _quit_callback(self):
        """
        Callback function for the Quit button. Quits the application if data
        has been submitted, otherwise displays an alert message.
        """
        if self.submitted:
            QCoreApplication.instance().quit()
        else:
            # alert
            msg = "Please, submit data before exit!"
            dlg = AlertMsg(self, msg)
            dlg.exec()

    def run(self, args):
        """
        entry point
        """
        self._navigation_buttons(args)

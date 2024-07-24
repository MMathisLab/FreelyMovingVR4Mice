from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout


class AlertMsg(QDialog):
    """
    A class for displaying an alert message dialog box.

    Args:
    parent (QWidget): The parent widget of the dialog box (default: None).
    msg (str): The message to be displayed in the dialog box (default: "").
    cancel (bool): A flag indicating whether to include a cancel button in addition to the OK button
    (default: False).

    """

    def __init__(self, parent=None, msg="", cancel=False):
        if msg == "":
            return False

        super().__init__(parent)

        self.setWindowTitle("Attention!")

        if cancel:
            btn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        else:
            btn = QDialogButtonBox.Ok

        self.buttonBox = QDialogButtonBox(btn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QVBoxLayout()
        message = QLabel(msg)
        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox, alignment=Qt.AlignCenter)
        self.setLayout(self.layout)

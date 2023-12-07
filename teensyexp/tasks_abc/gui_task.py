"""
    Contains definition of GuiTask
    that should be used for any task that requires a task-specific user interface, e.g., to deliver water manually.
    (don't inherit from ABC, but logically it's the abstract class)

"""
from teensyexp.tasks_abc.task import Task

class GuiTask(Task):
    """
        class representing Gui Task inherits from general Task class
    """
    def __init__(self, teensy):
        """
            class's constructor, use parent's constructor
            Args:
                teensy(Teensy object): instance of teensy class
        """
        super().__init__(teensy)

    def create_gui(self, parent):
        """
            gui implementation asked
            Returns:
                a tkinter window that provides the user with an interface to control the task during execution
            Note:
                the tkinter window must defined as `TopLevel(parent)`, rather than `Tk()`.
                This allows the task's GUI to update along with the TeensyExperiment GUI.
        """
        raise NotImplementedError

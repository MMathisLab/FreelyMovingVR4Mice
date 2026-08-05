import importlib
import importlib.util
import threading
import unittest
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "mouse_task"
    / "latency_tests"
    / "Teensy_latency"
    / "TeensyLatency.py"
)
_SPEC = importlib.util.spec_from_file_location("TeensyLatency_module", _MODULE_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)


class _FakeSerialException(Exception):
    pass


_SERIAL_STUB = types.SimpleNamespace(SerialException=_FakeSerialException)
with patch.dict(sys.modules, {"serial": _SERIAL_STUB}):
    _SPEC.loader.exec_module(_MODULE)
TeensyLatency = _MODULE.TeensyLatency


def _load_teensy_experiment_gui():
    try:
        from teensyexp.teensy_experiment import TeensyExperimentGUI
        return TeensyExperimentGUI
    except ModuleNotFoundError as err:
        if err.name != "serial":
            raise
        with patch.dict(sys.modules, {"serial": MagicMock()}):
            module = importlib.import_module("teensyexp.teensy_experiment")
        return module.TeensyExperimentGUI


TeensyExperimentGUI = _load_teensy_experiment_gui()


class TestTeensyLatencyReadExceptions(unittest.TestCase):
    """Regression tests for serial-read close-race exception handling."""

    def _make_latency(self, readline_side_effect):
        latency = TeensyLatency.__new__(TeensyLatency)
        latency.reading_teensy = True
        latency.stop_event = threading.Event()
        latency.ser = MagicMock()
        latency.ser.readline.side_effect = readline_side_effect
        latency.input_data = []
        latency.input_data_time = []
        return latency

    def test_known_windows_byref_typeerror_is_swallowed(self):
        latency = self._make_latency(
            TypeError("byref() argument must be a ctypes instance, not 'NoneType'")
        )

        latency.read_on_thread()

        self.assertEqual(latency.ser.readline.call_count, 1)

    def test_unrelated_typeerror_is_raised(self):
        latency = self._make_latency(TypeError("unexpected type problem"))

        with self.assertRaises(TypeError):
            latency.read_on_thread()


class TestTeensyGuiCloseBehavior(unittest.TestCase):
    """Regression tests for GUI close behavior and Ctrl+C handling."""

    def test_check_close_unsaved_uses_parented_warning(self):
        gui = TeensyExperimentGUI.__new__(TeensyExperimentGUI)
        gui.task_on = MagicMock()
        gui.task_on.get.return_value = 0
        gui.saved_ok = False
        gui.gui_on = True
        gui.window = object()

        with patch("teensyexp.teensy_experiment.messagebox.askokcancel", return_value=False) as askokcancel:
            gui.check_close()
            askokcancel.assert_called_once_with(
                "Exit",
                "ARE YOU SURE YOU SAVED YOUR Data?",
                parent=gui.window,
            )
            self.assertTrue(gui.gui_on)

        with patch("teensyexp.teensy_experiment.messagebox.askokcancel", return_value=True):
            gui.check_close()
            self.assertFalse(gui.gui_on)

    def test_run_experiment_repeated_keyboard_interrupt_still_closes(self):
        gui = TeensyExperimentGUI.__new__(TeensyExperimentGUI)
        gui.task_on_button = False
        gui.task_on = MagicMock()
        gui.task_on.get.return_value = 0
        gui.gui_task = None
        gui.gui_on = True

        class _FakeWindow:
            def __init__(self, owner):
                self.owner = owner
                self.calls = 0

            def update(self):
                self.calls += 1
                if self.calls == 1:
                    raise KeyboardInterrupt()
                self.owner.gui_on = False

        gui.window = _FakeWindow(gui)

        close_calls = []

        def _close_window():
            close_calls.append(1)
            if len(close_calls) == 1:
                raise KeyboardInterrupt()

        gui.close_window = _close_window

        with patch(
            "teensyexp.teensy_experiment.messagebox.showwarning",
            side_effect=KeyboardInterrupt,
        ) as showwarning:
            gui.run_experiment()

        self.assertEqual(showwarning.call_count, 1)
        self.assertEqual(len(close_calls), 2)


if __name__ == "__main__":
    unittest.main()

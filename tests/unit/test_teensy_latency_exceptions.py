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


if __name__ == "__main__":
    unittest.main()

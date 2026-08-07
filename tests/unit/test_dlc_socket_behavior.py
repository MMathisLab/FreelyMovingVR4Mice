import threading
import time
import unittest
from collections import deque
from unittest.mock import MagicMock, patch

import numpy as np

from teensyexp.tasks_abc.dlc_deque_socket import DLCClient as DequeSocketClient
from teensyexp.tasks_abc.dlc_socket import DLCClient as ListSocketClient


class TestDlcSocketCloseBehavior(unittest.TestCase):
    """Regression tests for deterministic close behavior in DLC socket clients."""

    def _assert_close_waits_for_reader_shutdown(self, client_cls):
        connect_started = threading.Event()

        def _blocking_connect(self):
            connect_started.set()
            time.sleep(2.2)
            raise TimeoutError("simulated connect stall")

        with patch.object(client_cls, "_connect_with_timeout", new=_blocking_connect):
            client = client_cls(address=("localhost", 6000))
            self.assertTrue(connect_started.wait(timeout=1), "reader never reached connect")

            read_thread = client._read_thread
            self.assertTrue(read_thread.is_alive())

            start = time.monotonic()
            client.close()
            elapsed = time.monotonic() - start

            self.assertGreaterEqual(elapsed, 2.0)
            self.assertFalse(read_thread.is_alive())
            self.assertIsNone(getattr(client, "conn", None))

    def test_list_buffer_client_close_waits_for_thread_exit(self):
        self._assert_close_waits_for_reader_shutdown(ListSocketClient)

    def test_deque_buffer_client_close_waits_for_thread_exit(self):
        self._assert_close_waits_for_reader_shutdown(DequeSocketClient)


class _FakeConn:
    def __init__(self, recv_side_effects):
        self._recv_side_effects = list(recv_side_effects)
        self.closed = False

    def recv(self):
        if not self._recv_side_effects:
            raise EOFError()
        value = self._recv_side_effects.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def close(self):
        self.closed = True


class TestDlcSocketReadBehavior(unittest.TestCase):
    def _make_client_without_thread(self, client_cls):
        with patch.object(client_cls, "start_read_buffer", return_value=None):
            client = client_cls(address=("localhost", 6000))
        if isinstance(client, DequeSocketClient):
            client.input_data = deque()
        return client

    def _assert_one_payload_received(self, client, payload):
        if isinstance(client, ListSocketClient):
            self.assertEqual(len(client.input_data), 1)
            self.assertEqual(client.input_data[0][1], payload)
            self.assertIsInstance(client.input_data[0][0], float)
        else:
            self.assertEqual(list(client.input_data), [payload])

    def _assert_happy_path(self, client_cls):
        payload = {"x": 1, "y": 2}
        fake_conn = _FakeConn([payload, EOFError()])
        client = self._make_client_without_thread(client_cls)

        with patch.object(client, "_connect_with_timeout", return_value=fake_conn):
            client.read_on_thread()

        self._assert_one_payload_received(client, payload)
        self.assertFalse(client.reading)
        self.assertTrue(fake_conn.closed)
        self.assertIsNone(getattr(client, "conn", None))

    def test_list_buffer_happy_path_receives_payload(self):
        self._assert_happy_path(ListSocketClient)

    def test_deque_buffer_happy_path_receives_payload(self):
        self._assert_happy_path(DequeSocketClient)

    def _assert_timeout_retries_then_receives(self, client_cls):
        payload = "frame"
        fake_conn = _FakeConn([payload, EOFError()])
        client = self._make_client_without_thread(client_cls)

        attempts = {"count": 0}

        def _connect_attempt():
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise TimeoutError("retry")
            return fake_conn

        with patch.object(client, "_connect_with_timeout", side_effect=_connect_attempt):
            client.read_on_thread()

        self.assertEqual(attempts["count"], 3)
        self._assert_one_payload_received(client, payload)
        self.assertTrue(fake_conn.closed)

    def test_list_buffer_retries_timeouts_then_connects(self):
        self._assert_timeout_retries_then_receives(ListSocketClient)

    def test_deque_buffer_retries_timeouts_then_connects(self):
        self._assert_timeout_retries_then_receives(DequeSocketClient)

    def _assert_recv_oserror_stops_reader(self, client_cls):
        fake_conn = _FakeConn([OSError("recv interrupted")])
        client = self._make_client_without_thread(client_cls)

        with patch.object(client, "_connect_with_timeout", return_value=fake_conn):
            client.read_on_thread()

        self.assertFalse(client.reading)
        self.assertTrue(fake_conn.closed)
        self.assertIsNone(getattr(client, "conn", None))

    def test_list_buffer_recv_oserror_stops_reader(self):
        self._assert_recv_oserror_stops_reader(ListSocketClient)

    def test_deque_buffer_recv_oserror_stops_reader(self):
        self._assert_recv_oserror_stops_reader(DequeSocketClient)

    def _assert_non_timeout_connect_exception_propagates(self, client_cls):
        client = self._make_client_without_thread(client_cls)

        with patch.object(client, "_connect_with_timeout", side_effect=ValueError("bad connect")):
            with self.assertRaises(ValueError):
                client.read_on_thread()

        self.assertIsNone(getattr(client, "conn", None))

    def test_list_buffer_non_timeout_connect_exception_propagates(self):
        self._assert_non_timeout_connect_exception_propagates(ListSocketClient)

    def test_deque_buffer_non_timeout_connect_exception_propagates(self):
        self._assert_non_timeout_connect_exception_propagates(DequeSocketClient)


class TestDlcSocketPublicApi(unittest.TestCase):
    def _make_client_without_thread(self, client_cls):
        with patch.object(client_cls, "start_read_buffer", return_value=None):
            client = client_cls(address=("localhost", 6000))
        if isinstance(client, DequeSocketClient):
            client.input_data = deque()
        return client

    def _assert_close_is_idempotent(self, client_cls):
        client = self._make_client_without_thread(client_cls)
        client.conn = MagicMock()
        client._read_thread = None

        client.close()
        client.close()

        self.assertFalse(client.reading)
        self.assertTrue(client._stop_event.is_set())
        self.assertEqual(client.conn.close.call_count, 2)

    def test_list_buffer_close_is_idempotent(self):
        self._assert_close_is_idempotent(ListSocketClient)

    def test_deque_buffer_close_is_idempotent(self):
        self._assert_close_is_idempotent(DequeSocketClient)

    def test_list_buffer_read_returns_latest_item(self):
        client = self._make_client_without_thread(ListSocketClient)
        client.input_data = [[1.0, "old"], [2.0, "new"]]

        out = client.read()

        self.assertEqual(out["time"], 2.0)
        self.assertEqual(out["vals"], "new")

    def test_list_buffer_read_returns_none_when_empty(self):
        client = self._make_client_without_thread(ListSocketClient)
        client.input_data = []
        self.assertIsNone(client.read())

    def test_list_buffer_reset_clears_input_data(self):
        client = self._make_client_without_thread(ListSocketClient)
        client.input_data = [[1.0, "frame"]]

        client.reset()

        self.assertEqual(client.input_data, [])

    def test_list_buffer_get_input_data_returns_numpy_array(self):
        client = self._make_client_without_thread(ListSocketClient)
        client.input_data = [[1.0, "frame1"], [2.0, "frame2"]]

        out = client.get_input_data()

        self.assertIsInstance(out, np.ndarray)
        self.assertEqual(out.shape[0], 2)

    def test_deque_buffer_read_returns_none_when_empty(self):
        client = self._make_client_without_thread(DequeSocketClient)
        client.input_data = deque()
        self.assertIsNone(client.read())

    def test_deque_buffer_read_pops_latest_and_clears_queue(self):
        client = self._make_client_without_thread(DequeSocketClient)
        client.input_data = deque(["old", "new"])

        out = client.read()

        self.assertEqual(out["vals"], "new")
        self.assertEqual(out["previous"], 0)
        self.assertEqual(len(client.input_data), 0)
        self.assertEqual(client.previous, "new")

    def test_deque_buffer_reset_clears_input_data(self):
        client = self._make_client_without_thread(DequeSocketClient)
        client.input_data = deque(["frame"])

        client.reset()

        self.assertEqual(len(client.input_data), 0)

    def test_deque_buffer_get_input_data_returns_numpy_array(self):
        client = self._make_client_without_thread(DequeSocketClient)
        client.input_data = deque(["frame1", "frame2"])

        out = client.get_input_data()

        self.assertIsInstance(out, np.ndarray)
        self.assertEqual(out.shape[0], 2)


if __name__ == "__main__":
    unittest.main()

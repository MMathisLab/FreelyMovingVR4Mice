"""Unit tests for analysis.py helpers."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from analysis import DEFAULT_UNITY_ARENA_SIZE, resolve_unity_arena_size


def _gui_params_mock(row_count, unity_arena_size):
    restricted = MagicMock()
    restricted.__len__ = MagicMock(return_value=row_count)
    restricted.fetch1 = MagicMock(return_value=unity_arena_size)
    table = MagicMock()
    table.__and__ = MagicMock(return_value=restricted)
    return table


class TestResolveUnityArenaSize:
    @patch("analysis.vr4mice.GuiParams")
    def test_returns_stored_value(self, mock_gui_params_ctor):
        custom = np.array([-12.0, 12.0, -8.0, -4.0])
        mock_gui_params_ctor.return_value = _gui_params_mock(1, custom)

        result = resolve_unity_arena_size({"dataset": "Mouse_2024-01-01_1"})

        np.testing.assert_array_equal(result, custom)

    @patch("analysis.vr4mice.GuiParams")
    def test_missing_gui_params_row_uses_default(self, mock_gui_params_ctor):
        mock_gui_params_ctor.return_value = _gui_params_mock(0, None)

        result = resolve_unity_arena_size({"dataset": "Mouse_2024-01-01_1"})

        np.testing.assert_array_equal(result, DEFAULT_UNITY_ARENA_SIZE)

    @patch("analysis.vr4mice.GuiParams")
    def test_null_value_uses_default(self, mock_gui_params_ctor):
        mock_gui_params_ctor.return_value = _gui_params_mock(1, None)

        result = resolve_unity_arena_size({"dataset": "Mouse_2024-01-01_1"})

        np.testing.assert_array_equal(result, DEFAULT_UNITY_ARENA_SIZE)

    @patch("analysis.vr4mice.GuiParams")
    def test_invalid_length_raises(self, mock_gui_params_ctor):
        mock_gui_params_ctor.return_value = _gui_params_mock(1, [1.0, 2.0, 3.0])

        with pytest.raises(ValueError, match="must have length 4"):
            resolve_unity_arena_size({"dataset": "Mouse_2024-01-01_1"})

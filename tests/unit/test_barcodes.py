"""Unit tests for Teensy barcode decoding."""

from pathlib import Path

import numpy as np
import pytest

from barcodes import (
    BarcodeDecoderConfig,
    decode_teensy_barcodes,
    has_teensy_ttl_data,
    normalize_ttl_read,
)
from dlc_helpers import align_timestamps_to_step_time

SCHEMA_BARCODES_PY = (
    Path(__file__).parent.parent.parent
    / "dj_pipeline"
    / "vr4mice"
    / "schema"
    / "barcodes.py"
)


def _barcode_edges(value: int, *, start_ms: int):
    config = BarcodeDecoderConfig()
    edges_ms = [start_ms, start_ms + config.wrapper_duration_ms]
    level = 0
    bit_start = start_ms + 2 * config.wrapper_duration_ms
    for bit in range(config.bit_count):
        next_level = (value >> bit) & 1
        boundary = bit_start + bit * config.bit_duration_ms
        if next_level != level:
            edges_ms.append(boundary)
            level = next_level
    bit_end = bit_start + config.bit_count * config.bit_duration_ms
    if level:
        edges_ms.append(bit_end)
    edges_ms.extend(
        [bit_end + config.wrapper_duration_ms, bit_end + 2 * config.wrapper_duration_ms]
    )
    edges = np.asarray(sorted(set(edges_ms)), dtype=np.int64)
    states = (np.arange(len(edges)) % 2 == 0).astype(np.uint8)
    return edges, states


def _sample_edges(edges, edge_states, *, start_ms: int, stop_ms: int):
    times = np.arange(start_ms, stop_ms + 1, dtype=np.int64)
    states = np.zeros(times.shape, dtype=np.uint8)
    for edge, state in zip(edges, edge_states):
        states[times >= edge] = state
    return times, states


def test_normalize_ttl_read_casts_string_values_to_uint8():
    result = normalize_ttl_read(np.asarray(["0", "1", "1", "0"]))

    assert result.dtype == np.uint8
    assert result.tolist() == [0, 1, 1, 0]


@pytest.mark.parametrize("values", [["0", "2"], [0, 0.5], [["0", "1"]]])
def test_normalize_ttl_read_rejects_invalid_values(values):
    with pytest.raises(ValueError):
        normalize_ttl_read(values)


def test_has_teensy_ttl_data_requires_aligned_nonempty_arrays():
    assert has_teensy_ttl_data(
        {
            "teensy_time": np.asarray(["1", "2"]),
            "ttl_read": np.asarray(["0", "1"]),
        }
    )
    assert not has_teensy_ttl_data({})
    assert not has_teensy_ttl_data(
        {"teensy_time": np.asarray([]), "ttl_read": np.asarray([])}
    )
    assert not has_teensy_ttl_data(
        {"teensy_time": np.asarray(["1"]), "ttl_read": np.asarray(["0", "1"])}
    )


def test_decode_teensy_barcodes_from_string_samples():
    expected_value = 2**31 + 123
    edges, edge_states = _barcode_edges(expected_value, start_ms=100)
    times, states = _sample_edges(
        edges,
        edge_states,
        start_ms=0,
        stop_ms=1_200,
    )
    photodiode_times = 1_785_000_000 + times * 0.0015

    result = decode_teensy_barcodes(
        times.astype(str),
        states.astype(str),
        photodiode_times,
    )

    assert [event.value for event in result.events] == [expected_value]
    assert result.events[0].onset_sample == 100
    assert result.events[0].onset_time == pytest.approx(photodiode_times[100])
    assert result.quality["edge_count"] == len(edges)
    assert result.quality["decoded_count"] == 1


def test_decode_teensy_barcodes_returns_no_events_for_constant_signal():
    result = decode_teensy_barcodes(
        np.arange(10).astype(str),
        np.zeros(10, dtype=int).astype(str),
        np.arange(10, dtype=float),
    )

    assert result.events == ()
    assert result.quality["edge_count"] == 0


@pytest.mark.parametrize(
    ("times", "states", "photodiode_times", "message"),
    [
        ([0, 1], [0], [10, 11], "same shape"),
        ([0, 1], [0, 1], [10], "same shape"),
        ([1, 0], [0, 1], [10, 11], "non-decreasing"),
    ],
)
def test_decode_teensy_barcodes_validates_sample_arrays(
    times, states, photodiode_times, message
):
    with pytest.raises(ValueError, match=message):
        decode_teensy_barcodes(times, states, photodiode_times)


def test_decode_teensy_barcodes_allows_duplicate_times_with_same_ttl_state():
    result = decode_teensy_barcodes(
        [0, 0, 1, 2],
        [0, 0, 0, 0],
        [10.0, 10.0, 11.0, 12.0],
    )

    assert result.events == ()
    assert result.quality["edge_count"] == 0


def test_align_timestamps_to_data_frame_step_time():
    step_time = np.asarray([0.10, 0.20, 0.30, 0.40])

    result = align_timestamps_to_step_time(
        np.asarray([0.14, 0.27, 0.39]),
        step_time,
    )

    assert result.tolist() == pytest.approx([0.10, 0.30, 0.40])


def test_align_timestamps_to_step_time_returns_nan_outside_step_range():
    step_time = np.asarray([0.10, 0.20, 0.30, 0.40])

    result = align_timestamps_to_step_time(
        np.asarray([0.05, 0.14, 0.45]),
        step_time,
    )

    assert np.isnan(result[0])
    assert result[1] == pytest.approx(0.10)
    assert np.isnan(result[2])


def test_teensy_barcodes_schema_allows_null_onset_time_unity():
    text = SCHEMA_BARCODES_PY.read_text()

    assert "onset_time_unity=NULL: float64" in text


def test_teensy_barcodes_make_converts_non_finite_unity_times_to_null():
    text = SCHEMA_BARCODES_PY.read_text()

    assert "if np.isfinite(onset_step_time)" in text
    assert "else None" in text

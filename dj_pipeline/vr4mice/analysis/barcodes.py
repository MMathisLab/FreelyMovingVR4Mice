"""Decode the laboratory's 32-bit digital barcodes from Teensy samples."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

import numpy as np

TEENSY_SAMPLE_RATE = 1_000.0


@dataclass(frozen=True)
class BarcodeDecoderConfig:
    """Timing parameters for the wrapper-plus-32-bit barcode waveform."""

    bit_count: int = 32
    inter_barcode_interval_ms: float = 5000.0
    wrapper_duration_ms: float = 10.0
    bit_duration_ms: float = 30.0
    tolerance_fraction: float = 0.2

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class DecodedBarcode:
    """One decoded barcode event in the source stream's native clock."""

    index: int
    value: int
    onset_sample: int
    onset_time: float


@dataclass(frozen=True)
class BarcodeDecodeResult:
    """Decoded events and signal-quality diagnostics."""

    events: tuple[DecodedBarcode, ...]
    quality: dict


def normalize_ttl_read(ttl_read) -> np.ndarray:
    """Return a one-dimensional uint8 array containing only zero and one."""
    states = np.asarray(ttl_read)
    if states.ndim != 1:
        raise ValueError("ttl_read must be one-dimensional")
    try:
        states = states.astype(np.float64)
    except (TypeError, ValueError) as error:
        raise ValueError("ttl_read values must be numeric zero or one") from error
    if not np.isfinite(states).all() or np.any((states != 0) & (states != 1)):
        raise ValueError("ttl_read values must contain only zero or one")
    return states.astype(np.uint8)


def has_teensy_ttl_data(proc_data) -> bool:
    """Return whether a PROC dictionary has aligned, non-empty Teensy TTL arrays."""
    if "teensy_time" not in proc_data or "ttl_read" not in proc_data:
        return False
    teensy_time = np.asarray(proc_data["teensy_time"])
    ttl_read = np.asarray(proc_data["ttl_read"])
    return (
        teensy_time.ndim == 1
        and ttl_read.ndim == 1
        and teensy_time.size > 0
        and teensy_time.size == ttl_read.size
    )


def decode_teensy_barcodes(
    teensy_time,
    ttl_read,
    photodiode_time,
    *,
    config: BarcodeDecoderConfig | None = None,
) -> BarcodeDecodeResult:
    """Decode Teensy TTL levels and attach their acquisition-clock timestamps."""
    try:
        times = np.asarray(teensy_time).astype(np.int64)
    except (TypeError, ValueError) as error:
        raise ValueError("teensy_time values must be integer milliseconds") from error
    states = normalize_ttl_read(ttl_read)
    try:
        continuous_times = np.asarray(photodiode_time).astype(np.float64)
    except (TypeError, ValueError) as error:
        raise ValueError("photodiode_time values must be numeric timestamps") from error

    if times.ndim != 1:
        raise ValueError("teensy_time must be one-dimensional")
    if continuous_times.ndim != 1:
        raise ValueError("photodiode_time must be one-dimensional")
    if times.shape != states.shape or times.shape != continuous_times.shape:
        raise ValueError(
            "teensy_time, ttl_read, and photodiode_time must have the same shape"
        )
    if times.size and np.any(np.diff(times) <= 0):
        raise ValueError("teensy_time must be strictly increasing")
    if not np.isfinite(continuous_times).all():
        raise ValueError("photodiode_time must contain only finite timestamps")

    edge_mask = states[1:] != states[:-1]
    edge_times = times[1:][edge_mask]
    edge_states = states[1:][edge_mask]
    edge_continuous_times = continuous_times[1:][edge_mask]
    result = decode_barcode_edges(
        edge_times,
        states=edge_states,
        sample_rate=TEENSY_SAMPLE_RATE,
        config=config,
    )
    onset_time_by_sample = dict(
        zip(edge_times.tolist(), edge_continuous_times.tolist(), strict=True)
    )
    events = tuple(
        replace(
            event,
            onset_time=float(onset_time_by_sample[event.onset_sample]),
        )
        for event in result.events
    )
    return replace(result, events=events)


def decode_barcode_edges(
    edge_samples: np.ndarray,
    *,
    sample_rate: float,
    states: np.ndarray | None = None,
    config: BarcodeDecoderConfig | None = None,
) -> BarcodeDecodeResult:
    """Decode wrapper-plus-32-bit barcodes from native-clock digital edges."""
    config = config or BarcodeDecoderConfig()
    edges = np.asarray(edge_samples, dtype=np.int64)
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if edges.ndim != 1:
        raise ValueError("edge_samples must be one-dimensional")
    if edges.size and np.any(np.diff(edges) <= 0):
        raise ValueError("edge_samples must be strictly increasing")
    if states is not None:
        edge_states = np.asarray(states, dtype=np.int8)
        if edge_states.shape != edges.shape:
            raise ValueError("states must have the same shape as edge_samples")
        edge_states = (edge_states > 0).astype(np.uint8)
        if edges.size and edge_states[0] == 0:
            edges = edges[1:]
            edge_states = edge_states[1:]
    if edges.size < 4:
        return BarcodeDecodeResult(events=(), quality=_quality_summary((), edges.size))

    sample_to_ms = 1000.0 / sample_rate
    edge_gaps_ms = np.diff(edges) * sample_to_ms
    wrapper_min = config.wrapper_duration_ms * (1 - config.tolerance_fraction)
    wrapper_max = config.wrapper_duration_ms * (1 + config.tolerance_fraction)
    wrapper_gaps = (edge_gaps_ms > wrapper_min) & (edge_gaps_ms < wrapper_max)
    wrappers = edges[:-1][wrapper_gaps]
    if wrappers.size > 1:
        remove = np.flatnonzero(np.diff(wrappers) * sample_to_ms < wrapper_max) + 1
        wrappers = np.delete(wrappers, remove)

    barcode_span_ms = (
        config.bit_count * config.bit_duration_ms + 6 * config.wrapper_duration_ms
    )
    if wrappers.size < 2:
        return BarcodeDecodeResult(events=(), quality=_quality_summary((), edges.size))
    starts = wrappers[:-1][np.diff(wrappers) * sample_to_ms < barcode_span_ms]

    on_times = edges[::2]
    off_times = edges[1::2]
    decoded: list[DecodedBarcode] = []
    start_index = 0
    while start_index < len(starts):
        start = int(starts[start_index])
        limit = start + barcode_span_ms * sample_rate / 1000
        on_code = on_times[(on_times > start) & (on_times < limit)]
        off_code = off_times[(off_times > start) & (off_times < limit)]
        if off_code.size == 0:
            start_index += 1
            continue

        current = off_code[0] + config.wrapper_duration_ms * sample_rate / 1000
        level_high = False
        value = 0
        tolerance = (
            config.bit_duration_ms * config.tolerance_fraction * sample_rate / 1000
        )
        for bit in range(config.bit_count):
            rising = np.any(
                (on_code >= current - tolerance) & (on_code <= current + tolerance)
            )
            falling = np.any(
                (off_code >= current - tolerance) & (off_code <= current + tolerance)
            )
            if rising:
                level_high = True
            elif falling:
                level_high = False
            if level_high:
                value |= 1 << bit
            current += config.bit_duration_ms * sample_rate / 1000

        decoded.append(
            DecodedBarcode(
                index=len(decoded),
                value=value,
                onset_sample=start,
                onset_time=start / sample_rate,
            )
        )
        start_index += 1
        minimum_interval_ms = config.inter_barcode_interval_ms * (
            1 - config.tolerance_fraction
        )
        minimum_next = start + minimum_interval_ms * sample_rate / 1000
        while start_index < len(starts) and starts[start_index] < minimum_next:
            start_index += 1

    events = tuple(event for event in decoded if event.value != 0)
    return BarcodeDecodeResult(
        events=events, quality=_quality_summary(events, edges.size)
    )


def _quality_summary(events: tuple[DecodedBarcode, ...], edge_count: int) -> dict:
    values = np.asarray([event.value for event in events], dtype=np.uint64)
    onsets = np.asarray([event.onset_sample for event in events], dtype=np.int64)
    return {
        "edge_count": int(edge_count),
        "decoded_count": len(events),
        "values_strictly_increment_by_one": bool(
            len(values) < 2 or np.all(np.diff(values) == 1)
        ),
        "onsets_strictly_increasing": bool(
            len(onsets) < 2 or np.all(np.diff(onsets) > 0)
        ),
        "duplicate_value_count": int(len(values) - len(np.unique(values))),
    }

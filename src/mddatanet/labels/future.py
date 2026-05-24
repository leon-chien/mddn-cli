"""Future-event and time-to-event label math."""

from __future__ import annotations

from collections.abc import MutableSequence, Sequence
from typing import Any


def future_event_labels(event_now: Sequence[bool], horizon_frames: int) -> list[bool]:
    """Return labels for whether an event occurs in `[t, t + horizon]`.

    This implementation keeps only a rolling count, so it is suitable for large
    boolean arrays once a chunk has been selected.
    """

    if horizon_frames < 0:
        raise ValueError("horizon_frames must be non-negative")
    n_frames = _sequence_len(event_now)
    output = [False] * n_frames
    active_count = 0
    for frame_index in range(n_frames - 1, -1, -1):
        exit_index = frame_index + horizon_frames + 1
        if exit_index < n_frames and bool(event_now[exit_index]):
            active_count -= 1
        if bool(event_now[frame_index]):
            active_count += 1
        output[frame_index] = active_count > 0
    return output


def time_to_event(event_now: Sequence[bool]) -> list[int]:
    """Return frames until next event, or -1 if no future event exists."""

    n_frames = _sequence_len(event_now)
    output = [-1] * n_frames
    next_event = -1
    for frame_index in range(n_frames - 1, -1, -1):
        if bool(event_now[frame_index]):
            next_event = frame_index
            output[frame_index] = 0
        elif next_event >= 0:
            output[frame_index] = next_event - frame_index
    return output


def write_future_event_labels(
    event_now: Any,
    output: MutableSequence[bool] | Any,
    *,
    horizon_frames: int,
    chunk_size: int = 65_536,
) -> None:
    """Chunked writer for future-event labels.

    The input and output can be Zarr arrays or sequence-like objects. Each chunk
    reads an overlap of `horizon_frames` beyond the write range.
    """

    n_frames = _sequence_len(event_now)
    for start in range(0, n_frames, chunk_size):
        end = min(start + chunk_size, n_frames)
        overlap_end = min(end + horizon_frames, n_frames)
        chunk = list(event_now[start:overlap_end])
        output[start:end] = future_event_labels(chunk, horizon_frames)[: end - start]


def write_future_event_labels_by_runs(
    event_now: Any,
    output: MutableSequence[bool] | Any,
    valid_mask: MutableSequence[bool] | Any,
    *,
    horizon_frames: int,
    run_ids: Any | None = None,
    chunk_size: int = 65_536,
) -> None:
    """Write fixed-horizon future labels without crossing run boundaries.

    A frame is valid only when the full horizon `[t, t + H]` is available within
    the same run. Invalid tail frames are written as false in both the future
    label and the valid mask.
    """

    n_frames = _sequence_len(event_now)
    for start, stop in _run_ranges(n_frames, run_ids):
        for chunk_start in range(start, stop, chunk_size):
            chunk_stop = min(chunk_start + chunk_size, stop)
            overlap_stop = min(chunk_stop + horizon_frames, stop)
            chunk = list(event_now[chunk_start:overlap_stop])
            future_chunk = future_event_labels(chunk, horizon_frames)[: chunk_stop - chunk_start]
            mask_chunk = [
                (frame_index + horizon_frames) < stop
                for frame_index in range(chunk_start, chunk_stop)
            ]
            output[chunk_start:chunk_stop] = [
                bool(value) and bool(mask)
                for value, mask in zip(future_chunk, mask_chunk, strict=True)
            ]
            valid_mask[chunk_start:chunk_stop] = mask_chunk


def write_time_to_event(
    event_now: Any,
    output: MutableSequence[int] | Any,
    *,
    chunk_size: int = 65_536,
) -> None:
    """Reverse chunked writer for time-to-event labels."""

    n_frames = _sequence_len(event_now)
    next_event = -1
    for end in range(n_frames, 0, -chunk_size):
        start = max(0, end - chunk_size)
        chunk = list(event_now[start:end])
        out_chunk = [-1] * len(chunk)
        for local_index in range(len(chunk) - 1, -1, -1):
            frame_index = start + local_index
            if bool(chunk[local_index]):
                next_event = frame_index
                out_chunk[local_index] = 0
            elif next_event >= 0:
                out_chunk[local_index] = next_event - frame_index
        output[start:end] = out_chunk


def write_time_to_event_by_runs(
    event_now: Any,
    output: MutableSequence[int] | Any,
    *,
    run_ids: Any | None = None,
    chunk_size: int = 65_536,
) -> None:
    """Write time-to-event labels without allowing events to cross run boundaries."""

    n_frames = _sequence_len(event_now)
    ranges = list(_run_ranges(n_frames, run_ids))
    for start, stop in reversed(ranges):
        next_event = -1
        for end in range(stop, start, -chunk_size):
            chunk_start = max(start, end - chunk_size)
            chunk = list(event_now[chunk_start:end])
            out_chunk = [-1] * len(chunk)
            for local_index in range(len(chunk) - 1, -1, -1):
                frame_index = chunk_start + local_index
                if bool(chunk[local_index]):
                    next_event = frame_index
                    out_chunk[local_index] = 0
                elif next_event >= 0:
                    out_chunk[local_index] = next_event - frame_index
            output[chunk_start:end] = out_chunk


def fixed_horizon_valid_mask(
    n_frames: int,
    horizon_frames: int,
    *,
    run_ids: Sequence[Any] | None = None,
) -> list[bool]:
    """Return true where a full future horizon is available in the same run."""

    mask = [False] * n_frames
    for start, stop in _run_ranges(n_frames, run_ids):
        for frame_index in range(start, stop):
            mask[frame_index] = (frame_index + horizon_frames) < stop
    return mask


def _sequence_len(values: Any) -> int:
    try:
        return len(values)
    except TypeError:
        shape = getattr(values, "shape", None)
        if shape is None:
            raise
        return int(shape[0])


def _run_ranges(n_frames: int, run_ids: Any | None = None) -> list[tuple[int, int]]:
    if n_frames <= 0:
        return []
    if run_ids is None:
        return [(0, n_frames)]
    ranges: list[tuple[int, int]] = []
    start = 0
    current = _run_value(run_ids, 0)
    for index in range(1, n_frames):
        value = _run_value(run_ids, index)
        if value != current:
            ranges.append((start, index))
            start = index
            current = value
    ranges.append((start, n_frames))
    return ranges


def _run_value(run_ids: Any, index: int) -> str:
    return str(run_ids[index])

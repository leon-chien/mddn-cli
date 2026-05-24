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


def _sequence_len(values: Any) -> int:
    try:
        return len(values)
    except TypeError:
        shape = getattr(values, "shape", None)
        if shape is None:
            raise
        return int(shape[0])

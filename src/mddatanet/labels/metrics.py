"""Descriptive label and baseline dataset metrics."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, median
from typing import Any


DEFAULT_CHUNK_SIZE = 65_536


def compute_label_metrics(zarr_root: Any, *, chunk_size: int = DEFAULT_CHUNK_SIZE) -> dict[str, Any]:
    """Compute per-event descriptive metrics without reading coordinates."""

    if "labels" not in zarr_root:
        return {}
    run_ids = zarr_root["arrays"]["run_ids"] if "arrays" in zarr_root and "run_ids" in zarr_root["arrays"] else None
    metrics: dict[str, Any] = {}
    for event_name in sorted(zarr_root["labels"].keys()):
        event_group = zarr_root["labels"][event_name]
        if "event_now" not in event_group:
            continue
        event_now = event_group["event_now"]
        future_name = _future_label_name(event_group)
        future = event_group[future_name] if future_name else None
        valid_name = f"{future_name}_valid_mask" if future_name else None
        valid_mask = event_group[valid_name] if valid_name and valid_name in event_group else None
        time_to_event = event_group["time_to_event"] if "time_to_event" in event_group else None
        horizon = _horizon_from_name(future_name)
        metrics[event_name] = _compute_event_metrics(
            event_now=event_now,
            future=future,
            valid_mask=valid_mask,
            time_to_event=time_to_event,
            run_ids=run_ids,
            horizon_frames=horizon,
            chunk_size=chunk_size,
        )
    return metrics


def write_metrics_files(package_dir: str | Path, zarr_root: Any) -> dict[str, Any]:
    """Write label statistics and baseline metrics JSON files."""

    package_dir = Path(package_dir)
    metrics = compute_label_metrics(zarr_root)
    label_statistics = {
        event_name: {
            "event_now_positive_rate": values["event_now_positive_rate"],
            "valid_future_positive_rate": values["valid_future_positive_rate"],
            "valid_future_frame_count": values["valid_future_frame_count"],
            "horizon_frames": values["horizon_frames"],
        }
        for event_name, values in metrics.items()
    }
    (package_dir / "label_statistics.json").write_text(
        json.dumps(label_statistics, indent=2) + "\n",
        encoding="utf-8",
    )
    (package_dir / "baseline_metrics.json").write_text(
        json.dumps({"metric_type": "descriptive_dataset_metrics", "events": metrics}, indent=2) + "\n",
        encoding="utf-8",
    )
    return metrics


def read_metrics_file(package_dir: str | Path) -> dict[str, Any]:
    path = Path(package_dir) / "baseline_metrics.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _compute_event_metrics(
    *,
    event_now: Any,
    future: Any | None,
    valid_mask: Any | None,
    time_to_event: Any | None,
    run_ids: Any | None,
    horizon_frames: int | None,
    chunk_size: int,
) -> dict[str, Any]:
    n_frames = int(event_now.shape[0])
    total = positives = 0
    valid_total = valid_positives = 0
    finite_tte: list[int] = []
    segments = 0
    durations: list[int] = []
    transition_count = 0
    previous_event = False
    previous_run: str | None = None
    active_duration = 0

    for start in range(0, n_frames, chunk_size):
        stop = min(start + chunk_size, n_frames)
        now_chunk = event_now[start:stop]
        future_chunk = future[start:stop] if future is not None else None
        mask_chunk = valid_mask[start:stop] if valid_mask is not None else [True] * len(now_chunk)
        tte_chunk = time_to_event[start:stop] if time_to_event is not None else None
        run_chunk = run_ids[start:stop] if run_ids is not None else ["__single_run__"] * len(now_chunk)

        for local_index, now_value in enumerate(now_chunk):
            run_value = str(run_chunk[local_index])
            is_event = bool(now_value)
            if previous_run is not None and run_value != previous_run:
                if active_duration:
                    durations.append(active_duration)
                active_duration = 0
                previous_event = False
            if is_event and not previous_event:
                segments += 1
                transition_count += 1
            if is_event:
                active_duration += 1
            elif active_duration:
                durations.append(active_duration)
                active_duration = 0
            total += 1
            positives += int(is_event)
            if bool(mask_chunk[local_index]):
                valid_total += 1
                if future_chunk is not None:
                    valid_positives += int(bool(future_chunk[local_index]))
            if tte_chunk is not None and int(tte_chunk[local_index]) >= 0:
                finite_tte.append(int(tte_chunk[local_index]))
            previous_event = is_event
            previous_run = run_value

    if active_duration:
        durations.append(active_duration)

    return {
        "horizon_frames": horizon_frames,
        "frame_count": total,
        "event_now_positive_count": positives,
        "event_now_positive_rate": _rate(positives, total),
        "valid_future_frame_count": valid_total,
        "valid_future_positive_count": valid_positives,
        "valid_future_positive_rate": _rate(valid_positives, valid_total),
        "event_segment_count": segments,
        "average_event_duration_frames": float(mean(durations)) if durations else 0.0,
        "transition_count": transition_count,
        "transition_rate_per_1k_frames": _rate(transition_count * 1000.0, total),
        "finite_time_to_event_count": len(finite_tte),
        "mean_observed_time_to_event_frames": float(mean(finite_tte)) if finite_tte else None,
        "median_observed_time_to_event_frames": float(median(finite_tte)) if finite_tte else None,
        "metric_note": "Descriptive dataset metrics; not model baseline performance.",
    }


def _future_label_name(event_group: Any) -> str | None:
    names = [
        name
        for name in event_group.keys()
        if name.startswith("event_future_") and not name.endswith("_valid_mask")
    ]
    return sorted(names)[0] if names else None


def _horizon_from_name(name: str | None) -> int | None:
    if not name:
        return None
    try:
        return int(name.rsplit("_", 1)[-1])
    except ValueError:
        return None


def _rate(numerator: float, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0

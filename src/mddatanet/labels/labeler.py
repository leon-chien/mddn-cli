"""High-level label generation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from mddatanet.format.schema import EventConfig, EventDefinition
from mddatanet.labels.events import evaluate_event, referenced_features
from mddatanet.labels.future import future_event_labels, time_to_event
from mddatanet.utils.errors import LabelError


def generate_labels(
    event_config: EventConfig,
    features: Mapping[str, Sequence[Any]],
) -> dict[str, dict[str, list[bool] | list[int]]]:
    """Generate event_now, event_future_H, and time_to_event arrays."""

    _validate_references(event_config.events, features)
    generated: dict[str, dict[str, list[bool] | list[int]]] = {}
    for event in event_config.events:
        event_now = evaluate_event(event, features)
        horizon_name = f"event_future_{event.horizon_frames}"
        generated[event.name] = {
            "event_now": event_now,
            horizon_name: future_event_labels(event_now, event.horizon_frames),
            "time_to_event": time_to_event(event_now),
        }
    return generated


def _validate_references(events: Sequence[EventDefinition], features: Mapping[str, Sequence[Any]]) -> None:
    missing: dict[str, set[str]] = {}
    for event in events:
        event_missing = referenced_features(event) - set(features)
        if event_missing:
            missing[event.name] = event_missing
    if missing:
        details = "; ".join(f"{event}: {', '.join(sorted(names))}" for event, names in missing.items())
        raise LabelError(
            f"Event config references missing features: {details}",
            suggestion=f"Available features: {', '.join(sorted(features)) or 'none'}.",
        )


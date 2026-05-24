"""Event rule evaluation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from mddatanet.format.schema import EventCondition, EventDefinition
from mddatanet.utils.errors import LabelError


def evaluate_event(event: EventDefinition, features: Mapping[str, Sequence[Any]]) -> list[bool]:
    """Evaluate an event definition against feature arrays."""

    if event.type == "feature_threshold":
        values = _feature(features, event.feature)
        return [_compare(value, event.operator, event.threshold) for value in values]
    if event.type == "feature_window":
        values = _feature(features, event.feature)
        lower = _required(event.lower_bound, "lower_bound")
        upper = _required(event.upper_bound, "upper_bound")
        return [lower <= float(value) <= upper for value in values]
    if event.type == "feature_bool":
        return [bool(value) for value in _feature(features, event.feature)]
    if event.type == "composite":
        return _evaluate_composite(event, features)
    raise LabelError(f"Unsupported event type: {event.type}")


def referenced_features(event: EventDefinition) -> set[str]:
    if event.type == "composite":
        return {condition.feature for condition in event.conditions or []}
    return {event.feature} if event.feature else set()


def _evaluate_composite(event: EventDefinition, features: Mapping[str, Sequence[Any]]) -> list[bool]:
    conditions = event.conditions or []
    if not conditions:
        raise LabelError(f"Composite event '{event.name}' has no conditions")
    evaluated = [_evaluate_condition(condition, features) for condition in conditions]
    length = len(evaluated[0])
    for values in evaluated:
        if len(values) != length:
            raise LabelError(f"Composite event '{event.name}' condition lengths do not match")
    if event.logic == "all":
        return [all(values[index] for values in evaluated) for index in range(length)]
    if event.logic == "any":
        return [any(values[index] for values in evaluated) for index in range(length)]
    raise LabelError(f"Unsupported composite logic: {event.logic}")


def _evaluate_condition(condition: EventCondition, features: Mapping[str, Sequence[Any]]) -> list[bool]:
    return [_compare(value, condition.operator, condition.threshold) for value in _feature(features, condition.feature)]


def _feature(features: Mapping[str, Sequence[Any]], feature_name: str | None) -> Sequence[Any]:
    if not feature_name:
        raise LabelError("Event is missing feature name")
    if feature_name not in features:
        available = ", ".join(sorted(features)) or "none"
        raise LabelError(
            f"Event references missing feature '{feature_name}'.",
            suggestion=f"Available features: {available}.",
        )
    return features[feature_name]


def _compare(value: Any, operator: str | None, threshold: float | None) -> bool:
    operator = _required(operator, "operator")
    threshold = _required(threshold, "threshold")
    value = float(value)
    if operator == "greater_than":
        return value > threshold
    if operator == "greater_equal":
        return value >= threshold
    if operator == "less_than":
        return value < threshold
    if operator == "less_equal":
        return value <= threshold
    if operator == "equal":
        return value == threshold
    if operator == "not_equal":
        return value != threshold
    raise LabelError(f"Unsupported operator: {operator}")


def _required(value: Any, label: str) -> Any:
    if value is None:
        raise LabelError(f"Event is missing required field: {label}")
    return value


"""Preset placeholder substitution and resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mddatanet.utils.errors import PresetError


@dataclass(frozen=True)
class ResolvedPreset:
    name: str
    feature_config: dict[str, Any]
    event_config: dict[str, Any]
    params: dict[str, Any]
    source: dict[str, Any]


def resolve_preset(
    preset: dict[str, Any],
    *,
    args: dict[str, Any] | None = None,
    param_overrides: dict[str, Any] | None = None,
) -> ResolvedPreset:
    """Resolve a preset dictionary into feature and event configs."""

    args = args or {}
    param_overrides = param_overrides or {}
    name = str(preset.get("name") or "")
    if not name:
        raise PresetError("Preset is missing name")
    missing = [arg for arg in preset.get("required_args", []) if not args.get(arg)]
    if missing:
        raise PresetError(
            f"Preset '{name}' requires: {', '.join(missing)}",
            suggestion="Pass the required CLI arguments for this preset.",
        )
    params = dict(preset.get("default_params", {}))
    params.update(param_overrides)
    values = {**args, **params}
    features = _substitute(preset.get("features", []), values)
    event = _substitute(preset.get("event", {}), values)
    return ResolvedPreset(
        name=name,
        feature_config={"features": features},
        event_config={"events": [event]},
        params=params,
        source=preset,
    )


def validate_preset_definition(preset: dict[str, Any]) -> None:
    """Validate preset YAML structure without requiring runtime args."""

    name = str(preset.get("name") or "")
    if not name:
        raise PresetError("Preset is missing name")
    if not isinstance(preset.get("features"), list) or not preset["features"]:
        raise PresetError(f"Preset '{name}' must define at least one feature.")
    if not isinstance(preset.get("event"), dict) or not preset["event"]:
        raise PresetError(f"Preset '{name}' must define one event.")
    if "name" not in preset["event"] or "type" not in preset["event"]:
        raise PresetError(f"Preset '{name}' event must include name and type.")
    for feature in preset["features"]:
        if not isinstance(feature, dict) or "name" not in feature or "type" not in feature:
            raise PresetError(f"Preset '{name}' features must include name and type.")


def _substitute(value: Any, values: dict[str, Any]) -> Any:
    if isinstance(value, str):
        if value.startswith("{") and value.endswith("}"):
            key = value[1:-1]
            if key not in values:
                raise PresetError(f"Missing preset placeholder value: {key}")
            return values[key]
        return value.format(**values)
    if isinstance(value, list):
        return [_substitute(item, values) for item in value]
    if isinstance(value, dict):
        return {key: _substitute(item, values) for key, item in value.items()}
    return value

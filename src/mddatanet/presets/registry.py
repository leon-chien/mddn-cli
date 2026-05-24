"""Preset registry.

Preset YAML files are intentionally deferred in the source-first build phase.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from mddatanet.presets.builtins import BUILTIN_PRESETS
from mddatanet.utils.errors import PresetError
from mddatanet.utils.yaml import read_yaml


class PresetRegistry:
    def __init__(self) -> None:
        self._presets: dict[str, dict[str, Any]] = {}

    def load_directory(self, directory: str | Path) -> None:
        directory = Path(directory)
        if not directory.exists():
            return
        for path in sorted(directory.glob("*.yaml")):
            data = read_yaml(path)
            if not isinstance(data, Mapping) or "name" not in data:
                raise PresetError(f"Invalid preset file: {path}")
            self._presets[str(data["name"])] = dict(data)

    def register(self, preset: Mapping[str, Any]) -> None:
        if "name" not in preset:
            raise PresetError("Preset is missing name")
        self._presets[str(preset["name"])] = dict(preset)

    def get(self, name: str) -> dict[str, Any]:
        try:
            return self._presets[name]
        except KeyError as exc:
            raise PresetError(
                f"Unknown preset: {name}",
                suggestion="Run `mddatanet presets list` to see available presets.",
            ) from exc

    def names(self) -> list[str]:
        return sorted(self._presets)

    def categories(self) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for name, preset in self._presets.items():
            grouped.setdefault(str(preset.get("category", "uncategorized")), []).append(name)
        return {category: sorted(names) for category, names in sorted(grouped.items())}


registry = PresetRegistry()
for _preset in BUILTIN_PRESETS:
    registry.register(_preset)

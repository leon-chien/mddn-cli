"""YAML helpers with a single dependency gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mddatanet.utils.errors import DependencyError


def _yaml_module():
    try:
        import yaml
    except Exception as exc:  # pragma: no cover - depends on local env
        raise DependencyError("PyYAML", purpose="YAML parsing") from exc
    return yaml


def read_yaml(path: str | Path) -> Any:
    yaml = _yaml_module()
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_yaml(data: Any, path: str | Path) -> None:
    yaml = _yaml_module()
    with Path(path).open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


"""Read and write `metadata.json`."""

from __future__ import annotations

import json
from pathlib import Path

from mddatanet.format.schema import Metadata


def read_metadata(package_dir: str | Path) -> Metadata:
    path = Path(package_dir) / "metadata.json"
    with path.open("r", encoding="utf-8") as handle:
        return Metadata.model_validate(json.load(handle))


def write_metadata(package_dir: str | Path, metadata: Metadata) -> None:
    path = Path(package_dir) / "metadata.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(metadata.model_dump(mode="json", exclude_none=True), handle, indent=2)
        handle.write("\n")


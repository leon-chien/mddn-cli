"""Read and write `provenance.json`."""

from __future__ import annotations

import json
from pathlib import Path

from mddatanet.format.schema import Provenance


def read_provenance(package_dir: str | Path) -> Provenance:
    path = Path(package_dir) / "provenance.json"
    with path.open("r", encoding="utf-8") as handle:
        return Provenance.model_validate(json.load(handle))


def write_provenance(package_dir: str | Path, provenance: Provenance) -> None:
    path = Path(package_dir) / "provenance.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(provenance.model_dump(mode="json", exclude_none=True), handle, indent=2)
        handle.write("\n")


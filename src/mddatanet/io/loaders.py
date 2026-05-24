"""MDAnalysis loader boundary.

The implementation is intentionally small in this source-first pass. The convert
and feature layers should use this boundary so trajectory loading can stay
streaming/chunked when the full MD implementation lands.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mddatanet.utils.errors import DependencyError, PackageError


def load_universe(
    topology: str | Path,
    *,
    coordinates: str | Path | None = None,
    trajectory: str | Path | None = None,
) -> Any:
    try:
        import MDAnalysis as mda
    except Exception as exc:  # pragma: no cover - depends on local env
        raise DependencyError("MDAnalysis", purpose="reading molecular dynamics files") from exc

    topology = Path(topology)
    if not topology.exists():
        raise PackageError(f"Topology file does not exist: {topology}")
    files = [str(topology)]
    if trajectory is not None:
        trajectory = Path(trajectory)
        if not trajectory.exists():
            raise PackageError(f"Trajectory file does not exist: {trajectory}")
        files.append(str(trajectory))
    elif coordinates is not None:
        coordinates = Path(coordinates)
        if not coordinates.exists():
            raise PackageError(f"Coordinate file does not exist: {coordinates}")
        files.append(str(coordinates))
    return mda.Universe(*files)

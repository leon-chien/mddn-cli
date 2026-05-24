"""Trajectory frame backend abstractions."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mddatanet.io.loaders import load_universe


@dataclass(frozen=True)
class FrameRecord:
    package_index: int
    source_frame_index: int
    run_id: str
    positions: Any


class RawMDAnalysisBackend:
    """Iterate frames from raw MDAnalysis-readable source files."""

    def __init__(self, *, topology: Path, coordinates: Path | None, trajectory: Path | None, run_id: str) -> None:
        self.topology = topology
        self.coordinates = coordinates
        self.trajectory = trajectory
        self.run_id = run_id
        self.universe = load_universe(topology, coordinates=coordinates, trajectory=trajectory)

    def iter_frames(self, *, package_start: int, source_frames) -> Iterator[FrameRecord]:
        for offset, source_frame in enumerate(source_frames):
            self.universe.trajectory[int(source_frame)]
            yield FrameRecord(
                package_index=package_start + offset,
                source_frame_index=int(source_frame),
                run_id=self.run_id,
                positions=self.universe.atoms.positions,
            )


class StoredPositionsBackend:
    """Iterate frames from positions stored in a package Zarr array."""

    def __init__(self, *, topology: Path, coordinates: Path | None, positions, run_id: str) -> None:
        self.topology = topology
        self.coordinates = coordinates
        self.positions = positions
        self.run_id = run_id
        self.universe = load_universe(topology, coordinates=coordinates, trajectory=None)

    def iter_frames(self, *, package_start: int, source_frames) -> Iterator[FrameRecord]:
        for offset, source_frame in enumerate(source_frames):
            package_index = package_start + offset
            self.universe.atoms.positions = self.positions[package_index]
            yield FrameRecord(
                package_index=package_index,
                source_frame_index=int(source_frame),
                run_id=self.run_id,
                positions=self.universe.atoms.positions,
            )


"""Minimal framework-agnostic dataset loader for trajectory windows."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np

from mddatanet.format.metadata import read_metadata
from mddatanet.io.layout import positions_array, trajectory_group
from mddatanet.io.package import PackageHandle, open_package
from mddatanet.io.zarr_store import open_zarr_group
from mddatanet.utils.errors import PackageError


class MDDataNetDataset:
    """Iterate over coordinate windows and future-event labels.

    This first loader is intentionally NumPy/Python only. It requires embedded
    trajectory coordinates and skips invalid future-label tail frames by
    default so users do not accidentally train on incomplete horizons.
    """

    def __init__(
        self,
        package_path: str | Path,
        *,
        window_length: int,
        target: str,
    ) -> None:
        if window_length < 1:
            raise PackageError("window_length must be >= 1")
        self.package_path = Path(package_path)
        self.window_length = int(window_length)
        self.target = target
        self.event_name, self.label_name, self.valid_name = _parse_future_target(target)
        self._handle: PackageHandle = open_package(self.package_path)
        self._root = self._handle.__enter__().root
        self.metadata = read_metadata(self._root)
        self._zarr_root = open_zarr_group(self._root / "dataset.zarr", mode="r")
        self._trajectory = trajectory_group(self._zarr_root)
        self._positions = positions_array(self._zarr_root)
        if self._positions is None:
            self.close()
            raise PackageError(
                "MDDataNetDataset requires embedded trajectory/positions.",
                suggestion=(
                    "Use a compressed/full package, or download/attach the coordinate "
                    "store referenced by download.yaml before training."
                ),
            )
        if self.metadata.storage_profile == "linked" or self.metadata.data_mode == "features-only":
            self.close()
            raise PackageError(
                "MDDataNetDataset cannot train directly from linked or features-only packages.",
                suggestion="Use an embedded-coordinate package for coordinate-window training.",
            )
        self._event_group = self._label_group(self.event_name)
        if self.label_name not in self._event_group:
            self.close()
            raise PackageError(f"Target label not found: labels/{self.event_name}/{self.label_name}")
        if self.valid_name not in self._event_group:
            self.close()
            raise PackageError(f"Target valid mask not found: labels/{self.event_name}/{self.valid_name}")
        self._labels = self._event_group[self.label_name]
        self._valid = self._event_group[self.valid_name]
        self._frame_indices = self._trajectory["frame_indices"]
        self._source_frame_indices = self._trajectory["source_frame_indices"]
        self._trajectory_ids = self._trajectory["trajectory_ids"]
        self._run_ids = self._trajectory["run_ids"]
        self._samples = self._build_sample_starts()

    def __len__(self) -> int:
        return len(self._samples)

    def __getitem__(self, index: int) -> dict[str, Any]:
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        start = self._samples[index]
        stop = start + self.window_length
        label_index = stop - 1
        return {
            "coordinates": np.asarray(self._positions[start:stop, :, :]),
            "label": self._labels[label_index],
            "valid": self._valid[label_index],
            "frame_indices": np.asarray(self._frame_indices[start:stop]),
            "source_frame_indices": np.asarray(self._source_frame_indices[start:stop]),
            "trajectory_ids": np.asarray(self._trajectory_ids[start:stop]),
            "run_ids": np.asarray(self._run_ids[start:stop]),
            "target": self.target,
            "metadata": self.metadata.model_dump(mode="json"),
        }

    def __iter__(self) -> Iterator[dict[str, Any]]:
        for index in range(len(self)):
            yield self[index]

    def close(self) -> None:
        self._handle.__exit__(None, None, None)

    def __enter__(self) -> "MDDataNetDataset":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def __del__(self) -> None:
        handle = getattr(self, "_handle", None)
        if handle is not None:
            handle.__exit__(None, None, None)

    def _label_group(self, event_name: str) -> Any:
        labels = self._zarr_root["labels"]
        if event_name not in labels:
            raise PackageError(f"Event not found in package labels: {event_name}")
        return labels[event_name]

    def _build_sample_starts(self) -> list[int]:
        n_frames = int(self._positions.shape[0])
        starts: list[int] = []
        for start in range(0, n_frames - self.window_length + 1):
            stop = start + self.window_length
            label_index = stop - 1
            if not bool(self._valid[label_index]):
                continue
            if str(self._run_ids[start]) != str(self._run_ids[label_index]):
                continue
            starts.append(start)
        return starts


def _parse_future_target(target: str) -> tuple[str, str, str]:
    if "_future_" not in target:
        raise PackageError(
            f"Unsupported target: {target}",
            suggestion="Use a future-event target such as ligand_unbinding_future_500.",
        )
    event_name, horizon = target.rsplit("_future_", 1)
    if not event_name or not horizon.isdigit():
        raise PackageError(
            f"Unsupported target: {target}",
            suggestion="Use a future-event target such as ligand_unbinding_future_500.",
        )
    label_name = f"event_future_{horizon}"
    valid_name = f"{label_name}_valid"
    return event_name, label_name, valid_name

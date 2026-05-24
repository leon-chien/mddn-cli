"""Package-level split service."""

from __future__ import annotations

import json
from pathlib import Path

from mddatanet.format.dataset_card import write_dataset_card
from mddatanet.format.metadata import read_metadata, write_metadata
from mddatanet.format.provenance import read_provenance
from mddatanet.format.schema import SplitSummary
from mddatanet.io.checksums import write_checksums
from mddatanet.io.workspace import PackageWorkspace
from mddatanet.io.zarr_store import create_array, open_zarr_group
from mddatanet.splits.random_window import random_window_split
from mddatanet.splits.temporal import temporal_split, validate_split_indices
from mddatanet.utils.errors import MDDataNetError


def split_package(
    *,
    input_path: Path,
    out: Path,
    strategy: str = "temporal",
    train: float = 0.7,
    val: float = 0.15,
    test: float = 0.15,
    gap: int = 0,
    seed: int | None = None,
    overwrite: bool = False,
) -> Path:
    workspace = PackageWorkspace(input_path, out, overwrite=overwrite)
    with workspace as work_dir:
        metadata = read_metadata(work_dir)
        provenance = read_provenance(work_dir)
        splits = make_splits(
            strategy,
            metadata.system.num_frames,
            runs=provenance.runs,
            train=train,
            val=val,
            test=test,
            gap=gap,
            seed=seed,
        )
        validate_split_indices(splits, num_frames=metadata.system.num_frames)
        zarr_root = open_zarr_group(work_dir / "dataset.zarr", mode="a")
        split_group = zarr_root["splits"]
        for split_name, indices in splits.items():
            array = create_array(
                split_group,
                split_name,
                shape=(len(indices),),
                dtype="int64",
                chunks=(min(max(len(indices), 1), 65_536),),
                overwrite=True,
            )
            array[:] = indices
        (work_dir / "splits.json").write_text(
            json.dumps(
                {
                    "strategy": strategy,
                    "train": len(splits["train"]),
                    "val": len(splits["val"]),
                    "test": len(splits["test"]),
                    "gap": gap,
                    "seed": seed,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        metadata.splits = SplitSummary(
            strategy=strategy,
            train=len(splits["train"]),
            val=len(splits["val"]),
            test=len(splits["test"]),
            gap=gap,
        )
        write_metadata(work_dir, metadata)
        write_dataset_card(work_dir, metadata, provenance)
        write_checksums(work_dir)
        workspace.finalize()
    return out


def make_splits(
    strategy: str,
    num_frames: int,
    *,
    runs=None,
    train: float,
    val: float,
    test: float,
    gap: int,
    seed: int | None,
) -> dict[str, list[int]]:
    if strategy == "temporal":
        return temporal_split(num_frames, train=train, val=val, test=test, gap=gap)
    if strategy == "random_window":
        return random_window_split(num_frames, train=train, val=val, test=test, gap=gap, seed=seed)
    if strategy == "trajectory":
        return _trajectory_run_split(runs or [], train=train, val=val, test=test)
    raise MDDataNetError(f"Unknown split strategy: {strategy}")


def _trajectory_run_split(runs, *, train: float, val: float, test: float) -> dict[str, list[int]]:
    from mddatanet.splits.temporal import _validate_ratios

    _validate_ratios(train, val, test)
    if len(runs) <= 1:
        raise MDDataNetError(
            "trajectory split requires at least two stored runs.",
            suggestion="Use repeated --trajectory during convert, or choose --strategy temporal.",
        )
    ordered = sorted(runs, key=lambda run: run.run_id)
    train_count = int(len(ordered) * train)
    val_count = int(len(ordered) * val)
    if train_count == 0 and ordered:
        train_count = 1
    if val_count == 0 and len(ordered) - train_count > 1:
        val_count = 1
    train_runs = ordered[:train_count]
    val_runs = ordered[train_count : train_count + val_count]
    test_runs = ordered[train_count + val_count :]
    return {
        "train": _run_indices(train_runs),
        "val": _run_indices(val_runs),
        "test": _run_indices(test_runs),
    }


def _run_indices(runs) -> list[int]:
    values: list[int] = []
    for run in runs:
        values.extend(range(run.package_start, run.package_stop))
    return values

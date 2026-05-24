"""Randomized split strategy."""

from __future__ import annotations

import random

from mddatanet.splits.temporal import _validate_ratios, validate_split_indices


def random_window_split(
    num_frames: int,
    *,
    train: float = 0.7,
    val: float = 0.15,
    test: float = 0.15,
    gap: int = 0,
    seed: int | None = None,
) -> dict[str, list[int]]:
    """Randomly assign frame indices.

    This is a source-first implementation of the command surface. A later
    version should add explicit window objects and stronger leakage controls.
    """

    _validate_ratios(train, val, test)
    rng = random.Random(seed)
    indices = list(range(num_frames))
    if gap:
        indices = indices[:: gap + 1]
    rng.shuffle(indices)
    train_count = int(len(indices) * train)
    val_count = int(len(indices) * val)
    splits = {
        "train": sorted(indices[:train_count]),
        "val": sorted(indices[train_count : train_count + val_count]),
        "test": sorted(indices[train_count + val_count :]),
    }
    validate_split_indices(splits, num_frames=num_frames)
    return splits


"""Trajectory/run-based split strategy."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from mddatanet.splits.temporal import _validate_ratios, validate_split_indices


def trajectory_split(
    trajectory_ids: Sequence[str],
    *,
    train: float = 0.7,
    val: float = 0.15,
    test: float = 0.15,
) -> dict[str, list[int]]:
    """Split frames by trajectory/run identifier."""

    _validate_ratios(train, val, test)
    groups: dict[str, list[int]] = defaultdict(list)
    for frame_index, trajectory_id in enumerate(trajectory_ids):
        groups[str(trajectory_id)].append(frame_index)
    ordered_ids = sorted(groups)
    train_count = int(len(ordered_ids) * train)
    val_count = int(len(ordered_ids) * val)
    train_ids = set(ordered_ids[:train_count])
    val_ids = set(ordered_ids[train_count : train_count + val_count])
    test_ids = set(ordered_ids[train_count + val_count :])
    splits = {
        "train": _flatten(groups, train_ids),
        "val": _flatten(groups, val_ids),
        "test": _flatten(groups, test_ids),
    }
    validate_split_indices(splits, num_frames=len(trajectory_ids))
    return splits


def _flatten(groups: dict[str, list[int]], ids: set[str]) -> list[int]:
    values: list[int] = []
    for trajectory_id in sorted(ids):
        values.extend(groups[trajectory_id])
    return sorted(values)


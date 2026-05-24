"""Temporal split strategy."""

from __future__ import annotations

from mddatanet.utils.errors import ValidationError


def temporal_split(
    num_frames: int,
    *,
    train: float = 0.7,
    val: float = 0.15,
    test: float = 0.15,
    gap: int = 0,
) -> dict[str, list[int]]:
    """Split contiguous frame indices with optional gaps between splits."""

    _validate_ratios(train, val, test)
    if num_frames < 0:
        raise ValidationError("num_frames must be non-negative")
    if gap < 0:
        raise ValidationError("gap must be non-negative")

    train_count = int(num_frames * train)
    val_count = int(num_frames * val)
    test_count = num_frames - train_count - val_count

    train_start = 0
    train_stop = train_start + train_count
    val_start = min(train_stop + gap, num_frames)
    val_stop = min(val_start + val_count, num_frames)
    test_start = min(val_stop + gap, num_frames)
    test_stop = min(test_start + test_count, num_frames)

    return {
        "train": list(range(train_start, train_stop)),
        "val": list(range(val_start, val_stop)),
        "test": list(range(test_start, test_stop)),
    }


def validate_split_indices(splits: dict[str, list[int]], *, num_frames: int) -> None:
    seen: set[int] = set()
    for split_name, values in splits.items():
        for value in values:
            if value < 0 or value >= num_frames:
                raise ValidationError(f"{split_name} contains out-of-range index {value}")
            if value in seen:
                raise ValidationError(f"{split_name} overlaps at index {value}")
            seen.add(value)


def _validate_ratios(train: float, val: float, test: float) -> None:
    total = train + val + test
    if min(train, val, test) < 0:
        raise ValidationError("split ratios must be non-negative")
    if abs(total - 1.0) > 1e-6:
        raise ValidationError("split ratios must sum to 1.0")


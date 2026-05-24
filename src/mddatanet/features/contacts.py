"""Contact feature numerical helpers."""

from __future__ import annotations

from typing import Any

from mddatanet.features.distances import pairwise_min_distance


def has_contact(positions_a: Any, positions_b: Any, *, threshold_angstrom: float) -> bool:
    return pairwise_min_distance(positions_a, positions_b) <= threshold_angstrom


def contact_count(positions_a: Any, positions_b: Any, *, threshold_angstrom: float) -> int:
    import numpy as np

    a = np.asarray(positions_a, dtype=float)
    b = np.asarray(positions_b, dtype=float)
    diff = a[:, None, :] - b[None, :, :]
    distances = np.linalg.norm(diff, axis=2)
    return int((distances <= threshold_angstrom).sum())


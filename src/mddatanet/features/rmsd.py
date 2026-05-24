"""RMSD numerical helper."""

from __future__ import annotations

from typing import Any


def rmsd(positions: Any, reference_positions: Any) -> float:
    import numpy as np

    positions = np.asarray(positions, dtype=float)
    reference = np.asarray(reference_positions, dtype=float)
    if positions.shape != reference.shape:
        raise ValueError("positions and reference_positions must have the same shape")
    diff = positions - reference
    return float(np.sqrt((diff * diff).sum() / positions.shape[0]))


"""Distance feature numerical helpers."""

from __future__ import annotations

from typing import Any


def _np():
    import numpy as np

    return np


def center_of_geometry(positions: Any) -> Any:
    np = _np()
    values = np.asarray(positions, dtype=float)
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError("positions must have shape (n_atoms, 3)")
    return values.mean(axis=0)


def distance(point_a: Any, point_b: Any) -> float:
    np = _np()
    return float(np.linalg.norm(np.asarray(point_a, dtype=float) - np.asarray(point_b, dtype=float)))


def pairwise_min_distance(positions_a: Any, positions_b: Any) -> float:
    np = _np()
    a = np.asarray(positions_a, dtype=float)
    b = np.asarray(positions_b, dtype=float)
    if a.ndim != 2 or b.ndim != 2 or a.shape[1] != 3 or b.shape[1] != 3:
        raise ValueError("positions_a and positions_b must have shape (n_atoms, 3)")
    diff = a[:, None, :] - b[None, :, :]
    distances = np.linalg.norm(diff, axis=2)
    return float(distances.min())


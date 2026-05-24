"""Radius of gyration numerical helper."""

from __future__ import annotations

from typing import Any


def radius_of_gyration(positions: Any, masses: Any | None = None) -> float:
    import numpy as np

    positions = np.asarray(positions, dtype=float)
    if masses is None:
        center = positions.mean(axis=0)
        squared = ((positions - center) ** 2).sum(axis=1)
        return float(np.sqrt(squared.mean()))
    masses = np.asarray(masses, dtype=float)
    center = (positions * masses[:, None]).sum(axis=0) / masses.sum()
    squared = ((positions - center) ** 2).sum(axis=1)
    return float(np.sqrt((masses * squared).sum() / masses.sum()))


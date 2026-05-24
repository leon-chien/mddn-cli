"""Contact map helper."""

from __future__ import annotations

from typing import Any


def contact_map(positions: Any, *, threshold_angstrom: float) -> Any:
    import numpy as np

    positions = np.asarray(positions, dtype=float)
    diff = positions[:, None, :] - positions[None, :, :]
    distances = np.linalg.norm(diff, axis=2)
    return distances <= threshold_angstrom


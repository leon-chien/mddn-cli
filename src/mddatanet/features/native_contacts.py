"""Native contact fraction helper."""

from __future__ import annotations

from typing import Any


def native_contact_fraction(
    positions: Any,
    reference_positions: Any,
    *,
    threshold_angstrom: float,
) -> float:
    import numpy as np

    current = np.asarray(positions, dtype=float)
    reference = np.asarray(reference_positions, dtype=float)
    if current.shape != reference.shape:
        raise ValueError("positions and reference_positions must have the same shape")
    ref_dist = _pairwise_distances(reference)
    current_dist = _pairwise_distances(current)
    native_mask = ref_dist <= threshold_angstrom
    native_mask &= ~np.eye(native_mask.shape[0], dtype=bool)
    total_native = int(native_mask.sum())
    if total_native == 0:
        return 0.0
    retained = int((current_dist[native_mask] <= threshold_angstrom).sum())
    return float(retained / total_native)


def _pairwise_distances(positions: Any) -> Any:
    import numpy as np

    diff = positions[:, None, :] - positions[None, :, :]
    return np.linalg.norm(diff, axis=2)


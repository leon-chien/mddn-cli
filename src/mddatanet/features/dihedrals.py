"""Dihedral feature numerical helpers."""

from __future__ import annotations

from math import degrees
from typing import Any


def dihedral_angle(p0: Any, p1: Any, p2: Any, p3: Any, *, units: str = "degrees") -> float:
    import numpy as np

    p0 = np.asarray(p0, dtype=float)
    p1 = np.asarray(p1, dtype=float)
    p2 = np.asarray(p2, dtype=float)
    p3 = np.asarray(p3, dtype=float)

    b0 = -(p1 - p0)
    b1 = p2 - p1
    b2 = p3 - p2
    b1 /= np.linalg.norm(b1)

    v = b0 - np.dot(b0, b1) * b1
    w = b2 - np.dot(b2, b1) * b1
    x = np.dot(v, w)
    y = np.dot(np.cross(b1, v), w)
    angle = float(np.arctan2(y, x))
    return degrees(angle) if units == "degrees" else angle


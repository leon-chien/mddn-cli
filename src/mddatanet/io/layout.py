"""Package Zarr layout helpers."""

from __future__ import annotations

from typing import Any


def trajectory_group(root: Any) -> Any:
    if "trajectory" in root:
        return root["trajectory"]
    return root["arrays"]


def topology_group(root: Any) -> Any:
    if "topology" in root:
        return root["topology"]
    return root["arrays"]


def positions_array(root: Any) -> Any | None:
    if "trajectory" in root and "positions" in root["trajectory"]:
        return root["trajectory"]["positions"]
    if "arrays" in root and "positions" in root["arrays"]:
        return root["arrays"]["positions"]
    return None


def box_array(root: Any) -> Any | None:
    if "trajectory" in root and "box_vectors" in root["trajectory"]:
        return root["trajectory"]["box_vectors"]
    if "arrays" in root and "dimensions" in root["arrays"]:
        return root["arrays"]["dimensions"]
    return None


def frame_array(root: Any, name: str) -> Any:
    group = trajectory_group(root)
    return group[name]


def run_ids_array(root: Any) -> Any | None:
    group = trajectory_group(root)
    return group["run_ids"] if "run_ids" in group else None


def has_legacy_arrays(root: Any) -> bool:
    return "arrays" in root and "trajectory" not in root

"""Package validation and inspection."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mddatanet.format.metadata import read_metadata
from mddatanet.format.provenance import read_provenance
from mddatanet.io.checksums import verify_checksums
from mddatanet.io.package import open_package
from mddatanet.io.zarr_store import REQUIRED_ROOT_GROUPS, open_zarr_group, require_root_groups


@dataclass
class ValidationResult:
    checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def add_check(self, message: str) -> None:
        self.checks.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def add_error(self, message: str) -> None:
        self.errors.append(message)


def validate_package(package_path: str | Path, *, check_checksums: bool = True) -> ValidationResult:
    """Validate package layout and array shapes without loading full arrays."""

    result = ValidationResult()
    try:
        with open_package(package_path) as handle:
            root = handle.root
            _validate_files(root, result)
            metadata = _validate_metadata(root, result)
            provenance = _validate_provenance(root, result)
            zarr_root = _validate_zarr(root, result)
            if zarr_root is not None and metadata is not None:
                _validate_array_shapes(zarr_root, metadata.system.num_frames, result)
                if provenance is not None:
                    _validate_runs(zarr_root, metadata.system.num_frames, provenance, result)
                _validate_splits(zarr_root, metadata.system.num_frames, result)
            if check_checksums:
                _validate_checksums(root, result)
    except Exception as exc:  # keep validation user-facing
        result.add_error(str(exc))
    return result


def inspect_package(
    package_path: str | Path,
    *,
    include_features: bool = False,
    include_labels: bool = False,
    include_splits: bool = False,
) -> dict[str, Any]:
    """Return a lightweight package summary."""

    with open_package(package_path) as handle:
        root = handle.root
        metadata = read_metadata(root)
        provenance = read_provenance(root)
        summary: dict[str, Any] = {
            "dataset_name": metadata.dataset_name,
            "description": metadata.description,
            "system": metadata.system.model_dump(mode="json"),
            "features": metadata.features.model_dump(mode="json"),
            "labels": metadata.labels.model_dump(mode="json"),
            "splits": metadata.splits.model_dump(mode="json") if metadata.splits else None,
            "files": sorted(path.name for path in root.iterdir()),
            "validation_ok": validate_package(root).ok,
            "runs": [
                {
                    "run_id": run.run_id,
                    "num_frames": run.num_frames,
                    "trajectory_file": run.trajectory_file,
                    "trajectory_format": run.trajectory_format,
                    "reader": run.reader,
                }
                for run in provenance.runs
            ],
            "num_runs": len(provenance.runs) or metadata.system.num_runs,
        }
        zarr_path = root / "dataset.zarr"
        if zarr_path.exists():
            zarr_root = open_zarr_group(zarr_path, mode="r")
            if include_features and "features" in zarr_root:
                summary["feature_arrays"] = _array_listing(zarr_root["features"])
            if include_labels and "labels" in zarr_root:
                summary["label_arrays"] = _label_listing(zarr_root["labels"])
                summary["label_positive_rates"] = _label_positive_rates(zarr_root["labels"])
            if include_splits and "splits" in zarr_root:
                summary["split_arrays"] = _array_listing(zarr_root["splits"])
        return summary


def format_inspection(summary: dict[str, Any]) -> str:
    system = summary["system"]
    features = summary["features"]
    labels = summary["labels"]
    lines = [
        f"MDDataNet Package: {summary['dataset_name']}",
        "System:",
        f"  Type: {system.get('system_type')}",
        f"  Atoms: {system.get('num_atoms')}",
        f"  Residues: {system.get('num_residues')}",
        f"  Frames: {system.get('num_frames')}",
        f"  Runs: {summary.get('num_runs', system.get('num_runs', 1))}",
        f"  Timestep: {system.get('timestep_ps')} ps",
    ]
    runs = summary.get("runs") or []
    if runs:
        lines.append("Runs:")
        for run in runs:
            lines.append(
                f"  {run.get('run_id')}: {run.get('num_frames')} frames"
                f" ({run.get('trajectory_format') or 'unknown'}, {run.get('reader') or 'unknown reader'})"
            )
        lines.append("Trajectory split: ready" if len(runs) > 1 else "Trajectory split: needs multiple runs")
    lines.append("Features:")
    feature_names = features.get("feature_names") or []
    lines.extend([f"  {name}" for name in feature_names] or ["  none"])
    lines.append("Events:")
    event_names = labels.get("event_names") or []
    lines.extend([f"  {name}" for name in event_names] or ["  none"])
    if summary.get("splits"):
        lines.extend(["Splits:", f"  {summary['splits']}"])
    lines.extend(["Validation:", "  passed" if summary["validation_ok"] else "  failed"])
    return "\n".join(lines)


def format_inspection_json(summary: dict[str, Any]) -> str:
    return json.dumps(summary, indent=2)


def _validate_files(root: Path, result: ValidationResult) -> None:
    for filename in ("metadata.json", "provenance.json", "dataset.zarr"):
        if (root / filename).exists():
            result.add_check(f"{filename} exists")
        else:
            result.add_error(f"{filename} missing")
    if (root / "dataset_card.md").exists():
        result.add_check("dataset_card.md exists")
    else:
        result.add_warning("dataset_card.md missing")


def _validate_metadata(root: Path, result: ValidationResult):
    try:
        metadata = read_metadata(root)
    except Exception as exc:
        result.add_error(f"metadata.json invalid: {exc}")
        return None
    result.add_check("metadata.json valid")
    return metadata


def _validate_provenance(root: Path, result: ValidationResult):
    try:
        provenance = read_provenance(root)
    except Exception as exc:
        result.add_error(f"provenance.json invalid: {exc}")
        return None
    result.add_check("provenance.json valid")
    return provenance


def _validate_zarr(root: Path, result: ValidationResult):
    zarr_path = root / "dataset.zarr"
    if not zarr_path.exists():
        return None
    try:
        zarr_root = open_zarr_group(zarr_path, mode="r")
    except Exception as exc:
        result.add_error(f"dataset.zarr unreadable: {exc}")
        return None
    missing = require_root_groups(zarr_root)
    if missing:
        result.add_error(f"dataset.zarr missing groups: {', '.join(missing)}")
    else:
        result.add_check("dataset.zarr required groups valid")
    return zarr_root


def _validate_array_shapes(zarr_root: Any, num_frames: int, result: ValidationResult) -> None:
    arrays = zarr_root["arrays"] if "arrays" in zarr_root else None
    if arrays is not None:
        for name in ("frame_indices", "frame_times"):
            if name in arrays:
                _check_first_dim(arrays[name], num_frames, f"arrays/{name}", result)
            else:
                result.add_error(f"arrays/{name} missing")
        for name in ("atom_names", "residue_ids", "residue_names"):
            if name in arrays:
                result.add_check(f"arrays/{name} exists")
            else:
                result.add_warning(f"arrays/{name} missing")
        for name in ("source_frame_indices", "trajectory_ids", "run_ids"):
            if name in arrays:
                _check_first_dim(arrays[name], num_frames, f"arrays/{name}", result)
            else:
                result.add_warning(f"arrays/{name} missing")
    for feature_name in _group_keys(zarr_root["features"]):
        _check_first_dim(zarr_root["features"][feature_name], num_frames, f"features/{feature_name}", result)
    for event_name in _group_keys(zarr_root["labels"]):
        event_group = zarr_root["labels"][event_name]
        if "event_now" not in event_group:
            result.add_error(f"labels/{event_name}/event_now missing")
        if "time_to_event" not in event_group:
            result.add_error(f"labels/{event_name}/time_to_event missing")
        if not any(name.startswith("event_future_") for name in _group_keys(event_group)):
            result.add_error(f"labels/{event_name} missing event_future label")
        for label_name in _group_keys(event_group):
            _check_first_dim(event_group[label_name], num_frames, f"labels/{event_name}/{label_name}", result)
    if "index" in zarr_root:
        _validate_index(zarr_root, result)


def _validate_splits(zarr_root: Any, num_frames: int, result: ValidationResult) -> None:
    if "splits" not in zarr_root:
        return
    seen: set[int] = set()
    for split_name in ("train", "val", "test"):
        splits = zarr_root["splits"]
        if split_name not in splits:
            continue
        split_array = splits[split_name]
        for chunk_start in range(0, int(split_array.shape[0]), 65_536):
            chunk_stop = min(chunk_start + 65_536, int(split_array.shape[0]))
            for value in split_array[chunk_start:chunk_stop]:
                index = int(value)
                if index < 0 or index >= num_frames:
                    result.add_error(f"splits/{split_name} contains out-of-range index {index}")
                if index in seen:
                    result.add_error(f"splits/{split_name} overlaps at index {index}")
                seen.add(index)
    if seen:
        result.add_check("splits valid")


def _validate_runs(zarr_root: Any, num_frames: int, provenance: Any, result: ValidationResult) -> None:
    if not provenance.runs:
        result.add_warning("provenance has no run records")
        return
    total = 0
    seen_ids: set[str] = set()
    for run in provenance.runs:
        if run.run_id in seen_ids:
            result.add_error(f"duplicate run id in provenance: {run.run_id}")
        seen_ids.add(run.run_id)
        if run.package_stop > num_frames:
            result.add_error(f"run '{run.run_id}' package range exceeds frame count")
        if run.package_stop - run.package_start != run.num_frames:
            result.add_error(f"run '{run.run_id}' frame count does not match package range")
        total += run.num_frames
    if total != num_frames:
        result.add_error(f"run frame total {total} does not match frame count {num_frames}")
    else:
        result.add_check("run records valid")
    arrays = zarr_root["arrays"] if "arrays" in zarr_root else None
    if arrays is not None and "run_ids" in arrays:
        for run in provenance.runs:
            sample = arrays["run_ids"][run.package_start : min(run.package_stop, run.package_start + 1)]
            if len(sample) and str(sample[0]) != run.run_id:
                result.add_error(f"arrays/run_ids does not match provenance for run '{run.run_id}'")


def _validate_checksums(root: Path, result: ValidationResult) -> None:
    if not (root / "checksums.json").exists():
        result.add_warning("checksums.json missing")
        return
    ok, problems = verify_checksums(root)
    if ok:
        result.add_check("checksums valid")
    else:
        for problem in problems:
            result.add_error(problem)


def _check_first_dim(array: Any, expected: int, label: str, result: ValidationResult) -> None:
    shape = getattr(array, "shape", None)
    if not shape:
        result.add_error(f"{label} has no shape")
        return
    if int(shape[0]) != int(expected):
        result.add_error(f"{label} length {shape[0]} does not match frame count {expected}")
    else:
        result.add_check(f"{label} frame count valid")


def _array_listing(group: Any) -> dict[str, dict[str, Any]]:
    return {
        name: {"shape": tuple(group[name].shape), "dtype": str(group[name].dtype)}
        for name in _group_keys(group)
    }


def _label_listing(group: Any) -> dict[str, dict[str, dict[str, Any]]]:
    return {name: _array_listing(group[name]) for name in _group_keys(group)}


def _label_positive_rates(group: Any) -> dict[str, dict[str, float]]:
    rates: dict[str, dict[str, float]] = {}
    for event_name in _group_keys(group):
        event_rates: dict[str, float] = {}
        for array_name in _group_keys(group[event_name]):
            array = group[event_name][array_name]
            if str(array.dtype) not in {"bool", "bool_"} and not array_name.startswith("event_"):
                continue
            total = 0
            positives = 0
            for chunk_start in range(0, int(array.shape[0]), 65_536):
                chunk_stop = min(chunk_start + 65_536, int(array.shape[0]))
                values = array[chunk_start:chunk_stop]
                total += len(values)
                positives += int(values.sum())
            event_rates[array_name] = float(positives / total) if total else 0.0
        rates[event_name] = event_rates
    return rates


def _validate_index(zarr_root: Any, result: ValidationResult) -> None:
    index = zarr_root["index"]
    if "feature_names" in index:
        indexed = {str(value) for value in index["feature_names"][:]}
        actual = set(_group_keys(zarr_root["features"]))
        if indexed != actual:
            result.add_warning("index/feature_names does not match feature arrays")
        else:
            result.add_check("index/feature_names valid")
    if "event_names" in index:
        indexed = {str(value) for value in index["event_names"][:]}
        actual = set(_group_keys(zarr_root["labels"]))
        if indexed != actual:
            result.add_warning("index/event_names does not match label groups")
        else:
            result.add_check("index/event_names valid")


def _group_keys(group: Any) -> list[str]:
    return sorted(list(group.keys()))

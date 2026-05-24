"""Package validation and inspection."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mddatanet.format.metadata import read_metadata
from mddatanet.format.provenance import read_provenance
from mddatanet.io.checksums import verify_checksums
from mddatanet.io.layout import (
    has_legacy_arrays,
    positions_array,
    run_ids_array,
    topology_group,
    trajectory_group,
)
from mddatanet.io.package import open_package
from mddatanet.io.zarr_store import open_zarr_group, require_root_groups
from mddatanet.labels.future import future_event_labels
from mddatanet.labels.metrics import compute_label_metrics, read_metrics_file


@dataclass
class ValidationResult:
    checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def add_check(self, message: str) -> None:
        self.checks.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def add_error(self, message: str, suggestion: str | None = None) -> None:
        self.errors.append(message)
        if suggestion:
            self.suggestions.append(suggestion)


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
                _validate_array_shapes(zarr_root, metadata, result)
                if metadata.storage_profile == "linked":
                    _validate_download_yaml(root, result)
                if provenance is not None:
                    _validate_runs(zarr_root, metadata.system.num_frames, provenance, result)
                _validate_splits(zarr_root, metadata.system.num_frames, metadata, result)
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
            "data_mode": metadata.data_mode,
            "storage_profile": metadata.storage_profile,
            "coordinate_storage": metadata.coordinate_storage.model_dump(mode="json"),
            "sampling": metadata.sampling.model_dump(mode="json"),
            "trajectory_summary": metadata.trajectory_summary.model_dump(mode="json"),
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
            pos = positions_array(zarr_root)
            if pos is not None:
                summary["coordinate_array"] = {
                    "shape": tuple(pos.shape),
                    "dtype": str(pos.dtype),
                    "chunks": tuple(getattr(pos, "chunks", ()) or ()),
                    "approx_size_bytes": int(pos.size * pos.dtype.itemsize),
                }
            if include_features and "features" in zarr_root:
                summary["feature_arrays"] = _array_listing(zarr_root["features"])
            if include_labels and "labels" in zarr_root:
                summary["label_arrays"] = _label_listing(zarr_root["labels"])
                summary["label_positive_rates"] = _label_positive_rates(zarr_root["labels"])
                summary["baseline_metrics"] = read_metrics_file(root) or {
                    "metric_type": "descriptive_dataset_metrics",
                    "events": compute_label_metrics(zarr_root),
                }
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
        f"Data mode: {summary.get('data_mode')}",
        f"Storage profile: {summary.get('storage_profile')}",
    ]
    coordinate_storage = summary.get("coordinate_storage", {})
    lines.extend(
        [
            f"Coordinates included: {'yes' if coordinate_storage.get('included') else 'no'}",
            f"Coordinate dtype: {coordinate_storage.get('dtype') or 'n/a'}",
            f"Compression: {coordinate_storage.get('compression') or 'n/a'}",
            f"Chunk frames: {coordinate_storage.get('chunk_frames') or 'n/a'}",
            f"Chunk atoms: {coordinate_storage.get('chunk_atoms') or 'n/a'}",
            f"Stride: {summary.get('sampling', {}).get('stride')}",
            f"Quantized: {'yes' if coordinate_storage.get('quantized') else 'no'}",
        ]
    )
    if coordinate_storage.get("external"):
        lines.append(f"External coordinates: {coordinate_storage.get('download_file') or 'download.yaml'}")
    if summary.get("coordinate_array"):
        size_mb = summary["coordinate_array"]["approx_size_bytes"] / (1024 * 1024)
        lines.append(f"Approx coordinate array size: {size_mb:.2f} MiB")
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
    baseline_metrics = summary.get("baseline_metrics", {}).get("events", {})
    if baseline_metrics:
        lines.append("Label Metrics:")
        for event_name, values in baseline_metrics.items():
            lines.append(
                f"  {event_name}: now+ {values.get('event_now_positive_rate', 0.0):.3f}, "
                f"future+ {values.get('valid_future_positive_rate', 0.0):.3f} "
                f"({values.get('valid_future_frame_count', 0)} valid frames), "
                f"{values.get('transition_count', 0)} transitions"
            )
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
        result.add_error(f"metadata.json invalid: {exc}", suggestion="Check JSON syntax and required fields in metadata.json.")
        return None
    result.add_check("metadata.json valid")
    return metadata


def _validate_provenance(root: Path, result: ValidationResult):
    try:
        provenance = read_provenance(root)
    except Exception as exc:
        result.add_error(f"provenance.json invalid: {exc}", suggestion="Check JSON syntax in provenance.json.")
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
        result.add_error(f"dataset.zarr unreadable: {exc}", suggestion="Check for corrupt Zarr storage or permission issues.")
        return None
    missing = require_root_groups(zarr_root)
    if missing and has_legacy_arrays(zarr_root):
        result.add_warning("dataset.zarr uses legacy arrays/ layout; new packages write trajectory/ and topology/.")
        missing = [name for name in missing if name not in {"trajectory", "topology"}]
    if missing:
        result.add_error(
            f"dataset.zarr missing groups: {', '.join(missing)}",
            suggestion="The package might be partially generated. Try re-running conversion/featurization.",
        )
    else:
        result.add_check("dataset.zarr required groups valid")
    return zarr_root


def _validate_array_shapes(zarr_root: Any, metadata: Any, result: ValidationResult) -> None:
    num_frames = metadata.system.num_frames
    num_atoms = metadata.system.num_atoms
    _validate_trajectory_arrays(zarr_root, metadata, result)
    _validate_topology_arrays(zarr_root, num_atoms, result)
    for feature_name in _group_keys(zarr_root["features"]):
        _check_first_dim(zarr_root["features"][feature_name], num_frames, f"features/{feature_name}", result)
    for event_name in _group_keys(zarr_root["labels"]):
        event_group = zarr_root["labels"][event_name]
        if "event_now" not in event_group:
            result.add_error(f"labels/{event_name}/event_now missing", suggestion=f"Re-run `mddatanet label` for {event_name}.")
        if "time_to_event" not in event_group:
            result.add_error(f"labels/{event_name}/time_to_event missing")
        if not any(name.startswith("event_future_") for name in _group_keys(event_group)):
            result.add_error(f"labels/{event_name} missing event_future label")
        for label_name in _group_keys(event_group):
            _check_first_dim(event_group[label_name], num_frames, f"labels/{event_name}/{label_name}", result)
        _validate_future_labels(zarr_root, event_name, result)
    if "index" in zarr_root:
        _validate_index(zarr_root, result)


def _validate_trajectory_arrays(zarr_root: Any, metadata: Any, result: ValidationResult) -> None:
    num_frames = metadata.system.num_frames
    try:
        trajectory = trajectory_group(zarr_root)
    except KeyError:
        result.add_error("dataset.zarr/trajectory missing", suggestion="Re-run `mddatanet convert` with a current version.")
        return
    prefix = "arrays" if has_legacy_arrays(zarr_root) else "trajectory"
    for name in ("frame_indices", "frame_times"):
        if name in trajectory:
            _check_first_dim(trajectory[name], num_frames, f"{prefix}/{name}", result)
        else:
            result.add_error(f"{prefix}/{name} missing", suggestion=f"Critical trajectory array {name} is missing.")
    for name in ("source_frame_indices", "trajectory_ids", "run_ids"):
        if name in trajectory:
            _check_first_dim(trajectory[name], num_frames, f"{prefix}/{name}", result)
        else:
            result.add_error(f"{prefix}/{name} missing", suggestion=f"Critical multi-run trajectory array {name} is missing.")
    if "box_vectors" in trajectory:
        _check_first_dim(trajectory["box_vectors"], num_frames, f"{prefix}/box_vectors", result)
    elif "dimensions" in trajectory:
        _check_first_dim(trajectory["dimensions"], num_frames, f"{prefix}/dimensions", result)
    else:
        result.add_warning(f"{prefix}/box_vectors missing")

    positions = positions_array(zarr_root)
    coordinate_storage = metadata.coordinate_storage
    coordinates_required = (
        metadata.storage_profile in {"compressed", "full"}
        and metadata.data_mode != "features-only"
        and bool(coordinate_storage.included)
    )
    if coordinates_required and positions is None:
        result.add_error("trajectory/positions missing", suggestion="Use linked storage or rerun convert with coordinates included.")
    if positions is not None:
        if tuple(positions.shape) != (num_frames, metadata.system.num_atoms, 3):
            result.add_error(
                f"trajectory/positions shape {tuple(positions.shape)} does not match "
                f"({num_frames}, {metadata.system.num_atoms}, 3)"
            )
        else:
            result.add_check("trajectory/positions shape valid")
        if coordinate_storage.dtype and str(positions.dtype) != coordinate_storage.dtype:
            result.add_error(
                f"trajectory/positions dtype {positions.dtype} does not match metadata {coordinate_storage.dtype}"
            )
        else:
            result.add_check("trajectory/positions dtype valid")


def _validate_topology_arrays(zarr_root: Any, num_atoms: int, result: ValidationResult) -> None:
    try:
        topology = topology_group(zarr_root)
    except KeyError:
        result.add_error("dataset.zarr/topology missing", suggestion="Re-run `mddatanet convert` with a current version.")
        return
    prefix = "arrays" if has_legacy_arrays(zarr_root) else "topology"
    for name in ("atom_names", "residue_ids", "residue_names"):
        if name in topology:
            _check_first_dim(topology[name], num_atoms, f"{prefix}/{name}", result)
        else:
            result.add_error(f"{prefix}/{name} missing")
    for name in ("atom_types", "chain_ids", "masses", "charges"):
        if name in topology:
            _check_first_dim(topology[name], num_atoms, f"{prefix}/{name}", result)
        else:
            result.add_warning(f"{prefix}/{name} missing")


def _validate_download_yaml(root: Path, result: ValidationResult) -> None:
    import yaml

    download_path = root / "download.yaml"
    if not download_path.exists():
        result.add_error("download.yaml missing for linked package")
        return
    with download_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    coordinates = data.get("coordinates") or {}
    if not coordinates.get("url") or not coordinates.get("sha256"):
        result.add_error("download.yaml linked coordinates require url and sha256")
    else:
        result.add_check("download.yaml linked coordinates valid")


def _validate_splits(zarr_root: Any, num_frames: int, metadata: Any, result: ValidationResult) -> None:
    if "splits" not in zarr_root:
        return
    import numpy as np

    seen: dict[str, np.ndarray] = {}
    for split_name in ("train", "val", "test"):
        splits = zarr_root["splits"]
        if split_name not in splits:
            continue
        split_array = splits[split_name][:]
        if len(split_array) == 0:
            result.add_warning(f"splits/{split_name} is empty")
            continue
            
        # Basic range and overlap check
        if (split_array < 0).any() or (split_array >= num_frames).any():
            result.add_error(f"splits/{split_name} contains out-of-range indices")
        
        seen[split_name] = split_array

    # Check for overlaps between different splits
    names = list(seen.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a = set(seen[names[i]])
            b = set(seen[names[j]])
            overlap = a & b
            if overlap:
                result.add_error(
                    f"splits/{names[i]} and splits/{names[j]} overlap at {len(overlap)} indices.",
                    suggestion="Re-run `mddatanet split` to generate non-overlapping splits.",
                )

    # Check leakage gaps if strategy is temporal
    if metadata.splits and metadata.splits.strategy == "temporal" and metadata.splits.gap > 0:
        gap = metadata.splits.gap
        # For temporal split, we expect train < val < test typically.
        if "train" in seen and "val" in seen:
            max_train = seen["train"].max()
            min_val = seen["val"].min()
            if min_val - max_train <= gap:
                result.add_error(
                    f"Temporal gap between train and val is {min_val - max_train}, expected > {gap}.",
                    suggestion="Increase --gap in `mddatanet split` or check if data is sufficient.",
                )
        if "val" in seen and "test" in seen:
            max_val = seen["val"].max()
            min_test = seen["test"].min()
            if min_test - max_val <= gap:
                result.add_error(
                    f"Temporal gap between val and test is {min_test - max_val}, expected > {gap}.",
                    suggestion="Increase --gap in `mddatanet split`.",
                )

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
        result.add_error(
            f"run frame total {total} does not match frame count {num_frames}",
            suggestion="Run records might be corrupted. Check convert.py logs.",
        )
    else:
        result.add_check("run records valid")
    run_ids = run_ids_array(zarr_root)
    if run_ids is not None:
        for run in provenance.runs:
            sample = run_ids[run.package_start : min(run.package_stop, run.package_start + 1)]
            if len(sample) and str(sample[0]) != run.run_id:
                result.add_error(f"trajectory/run_ids does not match provenance for run '{run.run_id}'")


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


def _validate_future_labels(zarr_root: Any, event_name: str, result: ValidationResult) -> None:
    event_group = zarr_root["labels"][event_name]
    if "event_now" not in event_group:
        return
    future_names = [
        name
        for name in _group_keys(event_group)
        if name.startswith("event_future_")
        and not name.endswith("_valid")
        and not name.endswith("_valid_mask")
    ]
    run_ids = run_ids_array(zarr_root)
    for future_name in future_names:
        try:
            horizon = int(future_name.rsplit("_", 1)[-1])
        except ValueError:
            result.add_error(f"labels/{event_name}/{future_name} has invalid horizon suffix")
            continue
        mask_name = f"{future_name}_valid"
        if mask_name not in event_group:
            result.add_error(
                f"labels/{event_name}/{mask_name} missing",
                suggestion="Re-run `mddatanet label` to generate fixed-horizon validity masks.",
            )
            continue
        _check_first_dim(event_group[mask_name], event_group["event_now"].shape[0], f"labels/{event_name}/{mask_name}", result)
        if not _future_label_matches(
            event_group["event_now"],
            event_group[future_name],
            event_group[mask_name],
            horizon,
            run_ids=run_ids,
        ):
            result.add_error(
                f"labels/{event_name}/{future_name} does not match fixed-horizon semantics",
                suggestion="Re-run `mddatanet label` to regenerate future labels and valid masks.",
            )
        else:
            result.add_check(f"labels/{event_name}/{future_name} horizon semantics valid")


def _future_label_matches(
    event_now: Any,
    future: Any,
    valid_mask: Any,
    horizon: int,
    *,
    run_ids: Any | None,
    chunk_size: int = 65_536,
) -> bool:
    n_frames = int(event_now.shape[0])
    for start, stop in _run_ranges(n_frames, run_ids):
        for chunk_start in range(start, stop, chunk_size):
            chunk_stop = min(chunk_start + chunk_size, stop)
            overlap_stop = min(chunk_stop + horizon, stop)
            now_chunk = list(event_now[chunk_start:overlap_stop])
            expected_future = future_event_labels(now_chunk, horizon)[: chunk_stop - chunk_start]
            expected_mask = [
                (frame_index + horizon) < stop
                for frame_index in range(chunk_start, chunk_stop)
            ]
            expected_future = [
                bool(value) and bool(mask)
                for value, mask in zip(expected_future, expected_mask, strict=True)
            ]
            actual_future = [bool(value) for value in future[chunk_start:chunk_stop]]
            actual_mask = [bool(value) for value in valid_mask[chunk_start:chunk_stop]]
            if actual_future != expected_future or actual_mask != expected_mask:
                return False
    return True


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


def _run_ranges(n_frames: int, run_ids: Any | None = None) -> list[tuple[int, int]]:
    if n_frames <= 0:
        return []
    if run_ids is None:
        return [(0, n_frames)]
    ranges: list[tuple[int, int]] = []
    start = 0
    current = str(run_ids[0])
    for index in range(1, n_frames):
        value = str(run_ids[index])
        if value != current:
            ranges.append((start, index))
            start = index
            current = value
    ranges.append((start, n_frames))
    return ranges


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

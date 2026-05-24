"""Package-level label generation service."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from mddatanet.features.compute import compute_features_in_place
from mddatanet.format.dataset_card import write_dataset_card
from mddatanet.format.metadata import read_metadata, write_metadata
from mddatanet.format.provenance import read_provenance, write_provenance
from mddatanet.format.schema import EventConfig, FeatureConfig
from mddatanet.io.checksums import sha256_file, write_checksums
from mddatanet.io.layout import run_ids_array
from mddatanet.io.workspace import PackageWorkspace
from mddatanet.io.zarr_store import create_array, open_zarr_group, write_index_names
from mddatanet.labels.events import evaluate_event, referenced_features
from mddatanet.labels.future import write_future_event_labels_by_runs, write_time_to_event_by_runs
from mddatanet.labels.metrics import write_metrics_files
from mddatanet.presets.registry import registry as preset_registry
from mddatanet.presets.resolver import resolve_preset
from mddatanet.utils.errors import LabelError, MDDataNetError
from mddatanet.utils.yaml import read_yaml, write_yaml


def label_package(
    *,
    input_path: Path,
    out: Path,
    events_path: Path | None = None,
    preset: str | None = None,
    preset_yaml: Path | None = None,
    preset_args: dict[str, Any] | None = None,
    param_overrides: dict[str, Any] | None = None,
    overwrite: bool = False,
    command: str | None = None,
) -> Path:
    """Generate labels for an existing package."""

    if events_path is None and preset is None and preset_yaml is None:
        raise LabelError("One of events_path, preset, or preset_yaml is required.")
    if sum(value is not None for value in (events_path, preset, preset_yaml)) != 1:
        raise LabelError("Use exactly one of events_path, preset, or preset_yaml.")
    workspace = PackageWorkspace(input_path, out, overwrite=overwrite)
    with workspace as work_dir:
        if preset is not None or preset_yaml is not None:
            preset_definition = preset_registry.get(preset) if preset is not None else read_yaml(preset_yaml)
            resolved = resolve_preset(
                preset_definition,
                args=preset_args or {},
                param_overrides=param_overrides or {},
            )
            feature_config = FeatureConfig.model_validate(resolved.feature_config)
            zarr_root = open_zarr_group(work_dir / "dataset.zarr", mode="a")
            missing_features = [
                feature for feature in feature_config.features if feature.name not in zarr_root["features"]
            ]
            if missing_features:
                compute_features_in_place(work_dir, FeatureConfig(features=missing_features), config_base_dir=None)
                metadata = read_metadata(work_dir)
                feature_names = sorted(set(metadata.features.feature_names) | {feature.name for feature in missing_features})
                metadata.features.feature_names = feature_names
                metadata.features.num_features = len(feature_names)
                write_metadata(work_dir, metadata)
                write_index_names(zarr_root, feature_names=feature_names)
            event_config = EventConfig.model_validate(resolved.event_config)
            write_yaml(resolved.feature_config, work_dir / "feature_config.yaml")
            write_yaml(resolved.event_config, work_dir / "events.yaml")
            (work_dir / "presets_used.json").write_text(
                json.dumps({"presets": [resolved.__dict__]}, indent=2) + "\n",
                encoding="utf-8",
            )
            if preset_yaml is not None:
                user_preset_dir = work_dir / "user_presets"
                user_preset_dir.mkdir(exist_ok=True)
                shutil.copyfile(preset_yaml, user_preset_dir / preset_yaml.name)
        else:
            event_config = EventConfig.model_validate(read_yaml(events_path))
            shutil.copyfile(events_path, work_dir / "events.yaml")

        write_labels_in_place(work_dir, event_config)
        metadata = read_metadata(work_dir)
        provenance = read_provenance(work_dir)
        metadata.labels.event_names = [event.name for event in event_config.events]
        metadata.labels.num_events = len(metadata.labels.event_names)
        metadata.analysis_summary.num_features = metadata.features.num_features
        metadata.analysis_summary.num_events = metadata.labels.num_events
        if preset is not None or preset_yaml is not None:
            metadata.analysis_summary.presets_used = [event.name for event in event_config.events]
        if command:
            provenance.commands.append(command)
        if events_path is not None:
            provenance.event_config_checksum = sha256_file(events_path)
        else:
            provenance.event_config_checksum = sha256_file(work_dir / "events.yaml")
        zarr_root = open_zarr_group(work_dir / "dataset.zarr", mode="a")
        write_index_names(zarr_root, event_names=metadata.labels.event_names)
        
        write_metrics_files(work_dir, zarr_root)
        write_metadata(work_dir, metadata)
        write_provenance(work_dir, provenance)
        write_dataset_card(work_dir, metadata, provenance)
        write_checksums(work_dir)
        workspace.finalize()
    return out


def write_labels_in_place(package_dir: Path, event_config: EventConfig) -> None:
    metadata = read_metadata(package_dir)
    zarr_root = open_zarr_group(package_dir / "dataset.zarr", mode="a")
    _write_labels(zarr_root, event_config, metadata.system.num_frames)


def _write_labels(zarr_root: Any, event_config: EventConfig, num_frames: int) -> None:
    from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn

    feature_group = zarr_root["features"]
    label_group = zarr_root["labels"]
    run_ids = run_ids_array(zarr_root)
    feature_names = set(feature_group.keys())

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("Generating labels...", total=len(event_config.events))
        for event in event_config.events:
            progress.update(task, description=f"Event: {event.name}")
            missing = referenced_features(event) - feature_names
            if missing:
                available = ", ".join(sorted(feature_names)) or "none"
                raise MDDataNetError(
                    f"Event '{event.name}' references missing features: {', '.join(sorted(missing))}.",
                    suggestion=f"Available features: {available}.",
                )
            event_group = label_group.require_group(event.name)
            event_now = create_array(
                event_group,
                "event_now",
                shape=(num_frames,),
                dtype="bool",
                chunks=(min(max(num_frames, 1), 65_536),),
                overwrite=True,
            )
            _write_event_now(feature_group, event, event_now, num_frames)
            future = create_array(
                event_group,
                f"event_future_{event.horizon_frames}",
                shape=(num_frames,),
                dtype="bool",
                chunks=(min(max(num_frames, 1), 65_536),),
                overwrite=True,
            )
            valid_mask = create_array(
                event_group,
                f"event_future_{event.horizon_frames}_valid",
                shape=(num_frames,),
                dtype="bool",
                chunks=(min(max(num_frames, 1), 65_536),),
                overwrite=True,
            )
            tte = create_array(
                event_group,
                "time_to_event",
                shape=(num_frames,),
                dtype="int64",
                chunks=(min(max(num_frames, 1), 65_536),),
                overwrite=True,
            )
            write_future_event_labels_by_runs(
                event_now,
                future,
                valid_mask,
                horizon_frames=event.horizon_frames,
                run_ids=run_ids,
            )
            write_time_to_event_by_runs(event_now, tte, run_ids=run_ids)
            progress.update(task, advance=1)



def _write_event_now(feature_group: Any, event: Any, output: Any, num_frames: int) -> None:
    chunk_size = min(max(num_frames, 1), 65_536)
    feature_names = referenced_features(event)
    for start in range(0, num_frames, chunk_size):
        end = min(start + chunk_size, num_frames)
        features = {name: feature_group[name][start:end] for name in feature_names}
        output[start:end] = evaluate_event(event, features)

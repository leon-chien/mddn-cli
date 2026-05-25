"""Export Hub-ready metadata registry files."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field, RootModel

from mddatanet import __version__
from mddatanet.format.metadata import read_metadata
from mddatanet.format.provenance import read_provenance
from mddatanet.format.validation import validate_package
from mddatanet.io.checksums import sha256_file
from mddatanet.io.package import open_package
from mddatanet.utils.errors import PackageError, ValidationError
from mddatanet.utils.paths import is_package_zip
from mddatanet.utils.yaml import read_yaml, write_yaml

DOWNLOAD_NOTES = "Upload package to Hugging Face, Zenodo, S3/R2, GCS, or institutional storage."
HUB_SCHEMA_VERSION = "0.1.0"


class HubDownloadAsset(BaseModel):
    url: str
    sha256: str
    bytes: int = Field(ge=0)
    provider: str = "external"
    notes: str = DOWNLOAD_NOTES


class HubDownload(RootModel[dict[str, HubDownloadAsset]]):
    root: dict[str, HubDownloadAsset]


class HubManifest(BaseModel):
    manifest_version: str = HUB_SCHEMA_VERSION
    package_version: str = __version__
    schema_version: str = HUB_SCHEMA_VERSION
    data_format: str
    storage_profile: str
    paths: dict[str, str]
    arrays: dict[str, dict[str, Any]] = Field(default_factory=dict)
    extensions: dict[str, Any] = Field(default_factory=dict)


def export_manifest(
    package_path: Path,
    *,
    out: Path,
    download_url: str | None = None,
    dataset_id: str | None = None,
    verify_download: bool = False,
    overwrite: bool = False,
) -> Path:
    """Export Hub registry metadata for a validated package."""

    package_path = Path(package_path)
    out = Path(out)
    result = validate_package(package_path)
    if not result.ok:
        raise ValidationError(
            "Cannot export manifest for an invalid package.",
            suggestion="Run `mddatanet validate` and fix errors first.",
        )
    if out.exists():
        if not overwrite:
            raise PackageError(f"Output already exists: {out}", suggestion="Use --overwrite to replace it.")
        shutil.rmtree(out)
    out.mkdir(parents=True)

    with open_package(package_path) as handle:
        root = handle.root
        metadata = read_metadata(root)
        provenance = read_provenance(root)
        resolved_dataset_id = dataset_id or _dataset_id(metadata.dataset_name)
        events = _optional_yaml(root / "events.yaml").get("events", [])
        features = _optional_yaml(root / "feature_config.yaml").get("features", [])
        package_info = _package_info(package_path, resolved_dataset_id)
        if verify_download:
            _verify_download(download_url, package_info)

        hub_metadata = _hub_metadata(
            root=root,
            metadata=metadata,
            provenance=provenance,
            dataset_id=resolved_dataset_id,
            events=events,
        )
        manifest = HubManifest(
            data_format=_data_format(package_path),
            storage_profile=_hub_storage_profile(metadata.storage_profile),
            paths=_manifest_paths(metadata),
            arrays=_array_descriptors(metadata, events, features),
            extensions={
                "mddatanet_version": metadata.mddatanet_version or __version__,
                "source_format_version": metadata.format_version,
                "package": package_info,
            },
        )
        downloads = _download_assets(
            package_info=package_info,
            dataset_id=resolved_dataset_id,
            package_download_url=download_url,
            package_download_yaml=_optional_yaml(root / "download.yaml"),
        )
        checksums = _hub_checksums(downloads)

        (out / "metadata.json").write_text(
            json.dumps(hub_metadata, indent=2) + "\n",
            encoding="utf-8",
        )
        (out / "manifest.json").write_text(
            json.dumps(manifest.model_dump(mode="json", exclude_none=True), indent=2) + "\n",
            encoding="utf-8",
        )
        write_yaml(downloads, out / "download.yaml")
        (out / "checksums.json").write_text(
            json.dumps(checksums, indent=2) + "\n",
            encoding="utf-8",
        )
        _copy_if_exists(root / "dataset_card.md", out / "dataset_card.md")
        _copy_if_exists(root / "baseline_metrics.json", out / "baseline_metrics.json")
        _copy_if_exists(root / "label_statistics.json", out / "label_statistics.json")
        _write_citation(metadata.source.citation, out / "citation.bib")
    return out


def _hub_metadata(
    *,
    root: Path,
    metadata: Any,
    provenance: Any,
    dataset_id: str,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    task = _task_metadata(metadata, events)
    hub_metadata = {
        "dataset_name": dataset_id,
        "version": __version__,
        "task": task,
        "system": _system_metadata(metadata),
        "storage_profile": _hub_storage_profile(metadata.storage_profile),
        "coordinate_storage": _coordinate_storage(metadata),
        "splits": _split_metadata(metadata),
        "statistics": {
            "num_trajectories": metadata.trajectory_summary.num_trajectories,
            "total_frames": metadata.system.num_frames,
            "num_runs": metadata.system.num_runs,
            "num_atoms": metadata.system.num_atoms,
            "num_residues": metadata.system.num_residues,
        },
        "license": metadata.license or "unknown",
        "provenance": {
            "source_files": [
                source.model_dump(mode="json", exclude_none=True)
                for source in provenance.source_files
            ],
            "runs": [run.model_dump(mode="json", exclude_none=True) for run in provenance.runs],
            "commands": [
                command.command if hasattr(command, "command") else command
                for command in provenance.commands
            ],
        },
        "extensions": {
            "source_metadata_path": "metadata.json",
            "source_dataset_name": metadata.dataset_name,
            "source_description": metadata.description,
            "mddatanet_version": metadata.mddatanet_version or __version__,
            "feature_names": metadata.features.feature_names,
            "event_names": metadata.labels.event_names,
            "label_statistics": _optional_json(root / "label_statistics.json"),
        },
    }
    if metadata.source.citation:
        hub_metadata["citation"] = "See citation.bib"
    return hub_metadata


def _task_metadata(metadata: Any, events: list[dict[str, Any]]) -> dict[str, Any]:
    event = events[0] if events else {}
    target_event = event.get("name") or (metadata.labels.event_names[0] if metadata.labels.event_names else "unlabeled")
    horizon = event.get("horizon_frames")
    task = {
        "task_type": "future_event_prediction" if metadata.labels.event_names else "state_classification",
        "target_event": _dataset_id(str(target_event)),
        "input_type": "trajectory_window",
        "label_type": "binary_event_within_horizon" if metadata.labels.event_names else "unlabeled",
        "extensions": {
            "label_source": "rule_based" if metadata.labels.event_names else "none",
            "event_definition": event,
        },
    }
    if horizon is not None and int(horizon) >= 1:
        task["horizon_frames"] = int(horizon)
    elif metadata.labels.event_names:
        task["horizon_frames"] = 1
    return task


def _system_metadata(metadata: Any) -> dict[str, Any]:
    system_type = metadata.system.system_type or "other"
    if system_type == "unknown":
        system_type = "other"
    if metadata.system.ligand_present and system_type == "protein":
        system_type = "protein_ligand"
    system = {
        "system_type": system_type,
        "protein": metadata.system.protein or "unknown",
    }
    if metadata.system.ligand_present:
        system["ligand"] = "present"
    return system


def _coordinate_storage(metadata: Any) -> dict[str, Any]:
    return {
        "included": bool(metadata.coordinate_storage.included),
        "external": bool(metadata.coordinate_storage.external or metadata.storage_profile == "linked"),
        "format": metadata.coordinate_storage.format or "mddatanet_zip",
        "notes": (
            "Coordinates are embedded in the downloadable MDDataNet package."
            if metadata.coordinate_storage.included
            else "Coordinates are external and described in download.yaml."
        ),
    }


def _split_metadata(metadata: Any) -> dict[str, Any]:
    if metadata.splits is None or metadata.splits.strategy is None:
        return {"policy": "temporal_split", "notes": "No split arrays are recorded in this package."}
    policy = {
        "temporal": "temporal_split",
        "trajectory": "run_split",
        "random_window": "temporal_split",
    }.get(metadata.splits.strategy, "temporal_split")
    return {
        "policy": policy,
        "train": metadata.splits.train,
        "validation": metadata.splits.val,
        "test": metadata.splits.test,
        "notes": f"Generated by mddatanet split using strategy={metadata.splits.strategy}.",
    }


def _manifest_paths(metadata: Any) -> dict[str, str]:
    return {
        "root": "/",
        "trajectories": "dataset.zarr/trajectory/",
        "coordinates": metadata.coordinate_storage.path or "external:download.yaml",
        "features": "dataset.zarr/features/",
        "labels": "dataset.zarr/labels/",
        "splits": "dataset.zarr/splits/",
        "topology": "dataset.zarr/topology/",
        "metadata": "metadata.json",
    }


def _array_descriptors(
    metadata: Any,
    events: list[dict[str, Any]],
    features: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    arrays: dict[str, dict[str, Any]] = {
        "coordinates": {
            "path": metadata.coordinate_storage.path or "external:download.yaml",
            "dtype": metadata.coordinate_storage.dtype or "float32",
            "shape": [metadata.system.num_frames, metadata.system.num_atoms, 3],
            "description": "Trajectory coordinate tensor.",
        },
        "frame_indices": {
            "path": "dataset.zarr/trajectory/frame_indices",
            "dtype": "int64",
            "shape": [metadata.system.num_frames],
            "description": "Global package frame indices.",
        },
        "source_frame_indices": {
            "path": "dataset.zarr/trajectory/source_frame_indices",
            "dtype": "int64",
            "shape": [metadata.system.num_frames],
            "description": "Frame indices in the original source trajectory.",
        },
        "run_ids": {
            "path": "dataset.zarr/trajectory/run_ids",
            "dtype": "string",
            "shape": [metadata.system.num_frames],
            "description": "Run identity for leakage-safe splits.",
        },
    }
    for feature in features:
        name = feature.get("name")
        if name:
            arrays[f"feature_{name}"] = {
                "path": f"dataset.zarr/features/{name}",
                "shape": [metadata.system.num_frames],
                "description": f"Derived feature: {feature.get('type', 'unknown')}.",
            }
    for event in events:
        name = event.get("name")
        horizon = event.get("horizon_frames")
        if name:
            arrays[f"label_{name}_event_now"] = {
                "path": f"dataset.zarr/labels/{name}/event_now",
                "dtype": "bool",
                "shape": [metadata.system.num_frames],
                "description": "Current-frame event label.",
            }
        if name and horizon is not None:
            arrays[f"label_{name}_future_{horizon}"] = {
                "path": f"dataset.zarr/labels/{name}/event_future_{horizon}",
                "dtype": "bool",
                "shape": [metadata.system.num_frames],
                "description": "Fixed-horizon future-event label.",
            }
            arrays[f"label_{name}_future_{horizon}_valid"] = {
                "path": f"dataset.zarr/labels/{name}/event_future_{horizon}_valid",
                "dtype": "bool",
                "shape": [metadata.system.num_frames],
                "description": "True where the full future horizon exists.",
            }
    if metadata.splits is not None:
        for split_name in ("train", "val", "test"):
            count = getattr(metadata.splits, split_name)
            if count is not None:
                arrays[f"split_{split_name}"] = {
                    "path": f"dataset.zarr/splits/{split_name}",
                    "dtype": "int64",
                    "shape": [count],
                    "description": f"{split_name} split frame indices.",
                }
    return arrays


def _download_assets(
    *,
    package_info: dict[str, Any],
    dataset_id: str,
    package_download_url: str | None,
    package_download_yaml: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    package_url = package_download_url or _placeholder_url(dataset_id, package_info["filename"])
    assets = {
        "package": {
            "url": package_url,
            "sha256": package_info["sha256"],
            "bytes": package_info["size_bytes"],
            "provider": _provider(package_url),
            "notes": "MDDataNet package archive." if package_download_url else f"Placeholder URL. {DOWNLOAD_NOTES}",
        }
    }
    coordinates = package_download_yaml.get("coordinates")
    if isinstance(coordinates, dict) and coordinates.get("url") and coordinates.get("sha256"):
        coord_url = str(coordinates["url"])
        assets["coordinates"] = {
            "url": coord_url,
            "sha256": str(coordinates["sha256"]),
            "bytes": int(coordinates.get("bytes") or coordinates.get("size_bytes") or 0),
            "provider": _provider(coord_url),
            "notes": str(coordinates.get("notes") or "External coordinate store."),
        }
    topology = package_download_yaml.get("topology")
    if isinstance(topology, dict) and topology.get("url") and topology.get("sha256"):
        topology_url = str(topology["url"])
        assets["topology"] = {
            "url": topology_url,
            "sha256": str(topology["sha256"]),
            "bytes": int(topology.get("bytes") or topology.get("size_bytes") or 0),
            "provider": _provider(topology_url),
            "notes": str(topology.get("notes") or "External topology file."),
        }
    return assets


def _hub_checksums(downloads: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "sha256": asset["sha256"],
            "bytes": asset.get("bytes", 0),
            "source": "download.yaml",
            "notes": asset.get("notes", ""),
        }
        for name, asset in downloads.items()
    }


def _package_info(package_path: Path, dataset_id: str) -> dict[str, Any]:
    if package_path.is_file() and is_package_zip(package_path):
        return {
            "filename": package_path.name,
            "sha256": sha256_file(package_path),
            "size_bytes": package_path.stat().st_size,
        }
    if package_path.is_dir():
        checksums = package_path / "checksums.json"
        size = sum(path.stat().st_size for path in package_path.rglob("*") if path.is_file())
        return {
            "filename": f"{dataset_id}.mddatanet.zip",
            "sha256": sha256_file(checksums) if checksums.exists() else "",
            "size_bytes": size,
        }
    raise PackageError(f"Unsupported package path: {package_path}")


def _data_format(package_path: Path) -> str:
    if package_path.is_file() and is_package_zip(package_path):
        return "mddatanet_zip"
    if package_path.is_dir():
        return "directory"
    return "metadata_only"


def _hub_storage_profile(profile: str) -> str:
    return {
        "compressed": "compressed",
        "full": "full_package_external",
        "linked": "external_coordinates",
    }.get(profile, "metadata_only")


def _placeholder_url(dataset_id: str, filename: str) -> str:
    return f"https://example.org/mddatanet/{dataset_id}/{filename}"


def _provider(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc:
        return parsed.netloc
    return "external"


def _optional_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = read_yaml(path)
    return data if isinstance(data, dict) else {}


def _optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _copy_if_exists(source: Path, destination: Path) -> None:
    if source.exists():
        shutil.copyfile(source, destination)


def _write_citation(citation: str | None, destination: Path) -> None:
    if not citation:
        return
    destination.write_text(
        "@misc{mddatanet_dataset,\n"
        f"  note = {{{citation}}}\n"
        "}\n",
        encoding="utf-8",
    )


def _verify_download(download_url: str | None, package_info: dict[str, Any]) -> bool:
    if not download_url:
        raise ValidationError(
            "--verify-download requires --download-url.",
            suggestion="Pass a reachable external URL or omit --verify-download.",
        )
    request = Request(download_url, method="HEAD", headers={"User-Agent": "mddatanet/0.1"})
    try:
        with urlopen(request, timeout=15) as response:
            length = response.headers.get("Content-Length")
            if length is not None and int(length) != int(package_info["size_bytes"]):
                raise ValidationError(
                    "Download URL size does not match package size.",
                    suggestion="Check that --download-url points to the exported package file.",
                )
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(
            f"Could not verify download URL: {exc}",
            suggestion="Check the URL or retry without --verify-download.",
        ) from exc
    return True


def _dataset_id(name: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in name).strip("_") or "dataset"

"""Export Hub-ready metadata registry files."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

from mddatanet import __version__
from mddatanet.format.metadata import read_metadata
from mddatanet.format.provenance import read_provenance
from mddatanet.format.validation import inspect_package, validate_package
from mddatanet.io.checksums import sha256_file
from mddatanet.io.package import open_package
from mddatanet.utils.errors import PackageError, ValidationError
from mddatanet.utils.paths import is_package_zip
from mddatanet.utils.yaml import read_yaml, write_yaml

PLACEHOLDER_DOWNLOAD_URL = "TO_BE_PROVIDED"
DOWNLOAD_NOTES = "Upload package to Hugging Face, Zenodo, S3/R2, GCS, or institutional storage."
MANIFEST_SCHEMA_VERSION = "1.0"
DOWNLOAD_SCHEMA_VERSION = "1.0"


class HubDownload(BaseModel):
    schema_version: str = DOWNLOAD_SCHEMA_VERSION
    url: str
    sha256: str
    size_bytes: int = Field(ge=0)
    storage_provider: str = "external"
    verified: bool = False
    notes: str = DOWNLOAD_NOTES


class HubManifest(BaseModel):
    schema_version: str = MANIFEST_SCHEMA_VERSION
    dataset_id: str
    package: dict[str, Any]
    format_version: str
    mddatanet_version: str
    tags: dict[str, Any]
    summary: dict[str, Any]
    download: HubDownload
    provenance: dict[str, Any]
    baseline_metrics: dict[str, Any] | None = None


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
        package_summary = inspect_package(package_path, include_features=True, include_labels=True, include_splits=True)
        package_info = _package_info(package_path, resolved_dataset_id)
        download = HubDownload(
            url=download_url or PLACEHOLDER_DOWNLOAD_URL,
            sha256=package_info["sha256"],
            size_bytes=package_info["size_bytes"],
            verified=_verify_download(download_url, package_info) if verify_download else False,
        )
        manifest = HubManifest(
            dataset_id=resolved_dataset_id,
            package=package_info,
            format_version=metadata.format_version,
            mddatanet_version=metadata.mddatanet_version or __version__,
            tags=_structured_tags(root, metadata, package_summary),
            summary={
                "dataset_name": metadata.dataset_name,
                "description": metadata.description,
                "data_mode": metadata.data_mode,
                "storage_profile": metadata.storage_profile,
                "coordinate_storage": metadata.coordinate_storage.model_dump(mode="json"),
                "sampling": metadata.sampling.model_dump(mode="json"),
                "num_atoms": metadata.system.num_atoms,
                "num_residues": metadata.system.num_residues,
                "num_frames": metadata.system.num_frames,
                "num_runs": metadata.system.num_runs,
                "features": metadata.features.feature_names,
                "events": metadata.labels.event_names,
                "splits": metadata.splits.model_dump(mode="json") if metadata.splits else None,
            },
            download=download,
            provenance={
                "source_files": [
                    source.model_dump(mode="json", exclude_none=True)
                    for source in provenance.source_files
                ],
                "runs": [run.model_dump(mode="json", exclude_none=True) for run in provenance.runs],
            },
            baseline_metrics=_optional_json(root / "baseline_metrics.json") or None,
        )
        _copy_if_exists(root / "metadata.json", out / "metadata.json")
        _copy_if_exists(root / "dataset_card.md", out / "dataset_card.md")
        _copy_if_exists(root / "checksums.json", out / "checksums.json")
        _copy_if_exists(root / "baseline_metrics.json", out / "baseline_metrics.json")
        _copy_if_exists(root / "label_statistics.json", out / "label_statistics.json")
        _copy_if_exists(root / "download.yaml", out / "package_download.yaml")
        _write_citation(metadata.source.citation, out / "citation.bib")
        (out / "manifest.json").write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )
        write_yaml(download.model_dump(mode="json"), out / "download.yaml")
    return out


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


def _structured_tags(root: Path, metadata, summary: dict[str, Any]) -> dict[str, Any]:
    events = _optional_yaml(root / "events.yaml").get("events", [])
    presets = _optional_json(root / "presets_used.json").get("presets", [])
    features = _optional_yaml(root / "feature_config.yaml").get("features", [])
    split_strategy = metadata.splits.strategy if metadata.splits else None
    event = events[0] if events else {}
    preset = presets[0]["name"] if presets and isinstance(presets[0], dict) and "name" in presets[0] else None
    return {
        "system": metadata.tags.get("system", {"type": metadata.system.system_type}),
        "simulation": metadata.tags.get("simulation", metadata.simulation.model_dump(mode="json", exclude_none=True)),
        "task": {
            "task_type": "future_event_prediction" if metadata.labels.event_names else None,
            "event_family": event.get("name") or (metadata.labels.event_names[0] if metadata.labels.event_names else None),
            "horizon_frames": event.get("horizon_frames"),
            "label_source": "rule_based" if metadata.labels.event_names else None,
            "preset": preset,
        },
        "features": {
            "feature_types": sorted({feature.get("type") for feature in features if feature.get("type")}),
            "feature_names": metadata.features.feature_names,
        },
        "ml": {
            "split_strategy": split_strategy,
            "leakage_gap_frames": metadata.splits.gap if metadata.splits else None,
            "baseline_models": [],
        },
        "license": metadata.tags.get("license", {"data_license": metadata.license}),
        "storage": {
            "data_mode": metadata.data_mode,
            "storage_profile": metadata.storage_profile,
            "coordinates_included": metadata.coordinate_storage.included,
            "coordinates_external": metadata.coordinate_storage.external,
        },
    }


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

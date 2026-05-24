"""Hub-scale package splitting helpers."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from mddatanet.format.metadata import read_metadata, write_metadata
from mddatanet.io.checksums import write_checksums
from mddatanet.io.package import open_package, pack_package
from mddatanet.io.zarr_store import open_zarr_group
from mddatanet.utils.errors import PackageError
from mddatanet.utils.paths import ensure_can_write
from mddatanet.utils.yaml import write_yaml


def split_package_for_hub(
    *,
    input_path: Path,
    out_labels: Path,
    out_coordinates: Path,
    overwrite: bool = False,
) -> tuple[Path, Path]:
    """Split a package into lightweight labels and coordinate archives."""

    out_labels = ensure_can_write(out_labels, overwrite=overwrite)
    out_coordinates = ensure_can_write(out_coordinates, overwrite=overwrite)
    with open_package(input_path) as handle, TemporaryDirectory(prefix="mddatanet-split-package-") as temp:
        temp_root = Path(temp)
        labels_dir = temp_root / "labels.mddatanet"
        coordinates_dir = temp_root / "coordinates.zarr"
        shutil.copytree(handle.root, labels_dir)
        dataset_zarr = labels_dir / "dataset.zarr"
        zarr_root = open_zarr_group(dataset_zarr, mode="a")
        if "trajectory" not in zarr_root or "topology" not in zarr_root:
            raise PackageError("split-package requires a trajectory-first package.")
        if "positions" not in zarr_root["trajectory"]:
            raise PackageError(
                "split-package requires embedded trajectory/positions.",
                suggestion="Linked or features-only packages already keep coordinates external.",
            )

        coordinates_dir.mkdir(parents=True)
        shutil.copytree(dataset_zarr / "trajectory", coordinates_dir / "trajectory")
        shutil.copytree(dataset_zarr / "topology", coordinates_dir / "topology")

        shutil.rmtree(dataset_zarr / "trajectory" / "positions")
        metadata = read_metadata(labels_dir)
        metadata.storage_profile = "linked"
        metadata.coordinate_storage.included = False
        metadata.coordinate_storage.external = True
        metadata.coordinate_storage.path = None
        metadata.coordinate_storage.download_file = "download.yaml"
        write_metadata(labels_dir, metadata)
        write_yaml(
            {
                "coordinates": {
                    "url": out_coordinates.name,
                    "sha256": "computed-after-export",
                    "format": "zarr.zip",
                    "required_for_training": True,
                },
                "topology": {
                    "url": out_coordinates.name,
                    "sha256": "computed-after-export",
                    "format": "zarr.zip",
                },
            },
            labels_dir / "download.yaml",
        )

        if out_coordinates.exists():
            out_coordinates.unlink()
        _zip_directory(coordinates_dir, out_coordinates)
        import hashlib

        digest = hashlib.sha256()
        with out_coordinates.open("rb") as handle_file:
            for block in iter(lambda: handle_file.read(1024 * 1024), b""):
                digest.update(block)
        download = {
            "coordinates": {
                "url": out_coordinates.name,
                "sha256": digest.hexdigest(),
                "format": "zarr.zip",
                "required_for_training": True,
            },
            "topology": {
                "url": out_coordinates.name,
                "sha256": digest.hexdigest(),
                "format": "zarr.zip",
            },
        }
        write_yaml(download, labels_dir / "download.yaml")
        write_checksums(labels_dir)
        pack_package(labels_dir, out_labels, overwrite=overwrite)
    return out_labels, out_coordinates


def _zip_directory(source: Path, output_zip: Path) -> None:
    if output_zip.exists():
        output_zip.unlink()
    with zipfile.ZipFile(output_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=str(path.relative_to(source)))

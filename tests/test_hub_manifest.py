import json
import subprocess
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mddatanet.cli import app
from mddatanet.convert import convert_package
from mddatanet.hub import export_manifest
from mddatanet.io.checksums import sha256_file
from mddatanet.labels.service import label_package
from mddatanet.utils.yaml import read_yaml

from tests.helpers import write_tiny_multimodel_pdb


VALID_SHA = "a" * 64


def test_export_manifest_for_valid_zip(tmp_path):
    pdb = write_tiny_multimodel_pdb(tmp_path / "tiny.pdb")
    raw = tmp_path / "raw.mddatanet"
    labeled_zip = tmp_path / "labeled.mddatanet.zip"
    out = tmp_path / "tiny_ligand"
    convert_package(
        topology=pdb,
        trajectory=None,
        coordinates=None,
        name="tiny",
        out=raw,
        citation="doi:10.0000/example",
        overwrite=True,
    )
    label_package(
        input_path=raw,
        out=labeled_zip,
        preset="ligand_unbinding",
        preset_args={"ligand": "name CA", "pocket": "name N"},
        param_overrides={"distance_threshold": 1.5, "horizon_frames": 1},
        overwrite=True,
    )

    export_manifest(labeled_zip, out=out, dataset_id="tiny_ligand", overwrite=True)

    metadata = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    download = read_yaml(out / "download.yaml")
    checksums = json.loads((out / "checksums.json").read_text(encoding="utf-8"))
    exported = {path.name for path in out.iterdir()}
    assert (out / "metadata.json").exists()
    assert (out / "dataset_card.md").exists()
    assert (out / "checksums.json").exists()
    assert "package_download.yaml" not in exported
    assert metadata["dataset_name"] == "tiny_ligand"
    assert metadata["task"]["task_type"] == "future_event_prediction"
    assert metadata["task"]["target_event"] == "ligand_unbinding"
    assert metadata["task"]["horizon_frames"] == 1
    assert metadata["task"]["input_type"] == "trajectory_window"
    assert manifest["manifest_version"] == "0.1.0"
    assert manifest["data_format"] == "mddatanet_zip"
    assert manifest["storage_profile"] == "compressed"
    assert manifest["paths"]["coordinates"] == "dataset.zarr/trajectory/positions"
    assert download["package"]["sha256"] == sha256_file(labeled_zip)
    assert download["package"]["bytes"] == labeled_zip.stat().st_size
    assert download["package"]["url"].startswith("https://example.org/mddatanet/tiny_ligand/")
    assert checksums["package"]["sha256"] == download["package"]["sha256"]
    assert checksums["package"]["bytes"] == download["package"]["bytes"]
    assert (out / "citation.bib").exists()
    assert (out / "baseline_metrics.json").exists()
    assert (out / "label_statistics.json").exists()


def test_cli_export_manifest(tmp_path):
    pdb = write_tiny_multimodel_pdb(tmp_path / "tiny.pdb")
    package = tmp_path / "raw.mddatanet.zip"
    out = tmp_path / "hub"
    convert_package(topology=pdb, trajectory=None, coordinates=None, name="tiny", out=package, overwrite=True)

    result = CliRunner().invoke(app, ["export-manifest", str(package), "--out", str(out)])

    assert result.exit_code == 0
    assert (out / "manifest.json").exists()
    with zipfile.ZipFile(package) as archive:
        assert any(name.endswith("metadata.json") for name in archive.namelist())


def test_export_manifest_for_linked_coordinates(tmp_path):
    pdb = write_tiny_multimodel_pdb(tmp_path / "tiny.pdb")
    package = tmp_path / "linked.mddatanet.zip"
    out = tmp_path / "linked_dataset"
    convert_package(
        topology=pdb,
        trajectory=None,
        coordinates=None,
        name="linked_dataset",
        out=package,
        storage_profile="linked",
        coordinates_url="https://storage.example/coords.zarr.zip",
        coordinates_sha256=VALID_SHA,
        overwrite=True,
    )

    export_manifest(package, out=out, overwrite=True)

    metadata = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
    download = read_yaml(out / "download.yaml")
    checksums = json.loads((out / "checksums.json").read_text(encoding="utf-8"))
    assert metadata["storage_profile"] == "external_coordinates"
    assert metadata["coordinate_storage"]["external"]
    assert "coordinates" in download
    assert download["coordinates"]["sha256"] == VALID_SHA
    assert checksums["coordinates"]["sha256"] == download["coordinates"]["sha256"]


def test_export_manifest_validates_against_sibling_hub_schemas(tmp_path):
    jsonschema = pytest.importorskip("jsonschema")
    referencing = pytest.importorskip("referencing")
    yaml = pytest.importorskip("yaml")
    hub_root = Path(__file__).resolve().parents[1].parent / "mddn-hub"
    if not hub_root.exists():
        pytest.skip("sibling mddn-hub repository is not available")

    pdb = write_tiny_multimodel_pdb(tmp_path / "tiny.pdb")
    raw = tmp_path / "raw.mddatanet"
    package = tmp_path / "tiny_ligand.mddatanet.zip"
    out = tmp_path / "tiny_ligand"
    convert_package(topology=pdb, trajectory=None, coordinates=None, name="tiny_ligand", out=raw, overwrite=True)
    label_package(
        input_path=raw,
        out=package,
        preset="ligand_unbinding",
        preset_args={"ligand": "name CA", "pocket": "name N"},
        param_overrides={"distance_threshold": 1.5, "horizon_frames": 1},
        overwrite=True,
    )
    export_manifest(package, out=out, dataset_id="tiny_ligand", overwrite=True)

    _validate_hub_schema(
        jsonschema=jsonschema,
        referencing=referencing,
        yaml=yaml,
        hub_root=hub_root,
        entry_dir=out,
    )
    result = subprocess.run(
        [str(Path("/Users/leonchien/miniforge3/envs/mddatanet/bin/python")), str(hub_root / "scripts/validate_entry.py"), str(out)],
        cwd=hub_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 2 and "Missing validation dependency" in result.stderr:
        pytest.skip("Hub validation script dependencies are not installed")
    if "is not in the subpath of" in result.stderr:
        pytest.skip("Hub validation script expects entries inside the Hub repository")
    assert result.returncode == 0, result.stderr


def _validate_hub_schema(*, jsonschema, referencing, yaml, hub_root: Path, entry_dir: Path) -> None:
    from jsonschema import Draft202012Validator, FormatChecker
    from referencing import Registry, Resource

    schema_dir = hub_root / "schemas"
    schemas = {
        schema_path.name: json.loads(schema_path.read_text(encoding="utf-8"))
        for schema_path in schema_dir.glob("*.schema.json")
    }
    resources = []
    for schema_name, schema in schemas.items():
        resource = Resource.from_contents(schema)
        resources.append((schema_name, resource))
        resources.append((schema.get("$id", schema_name), resource))
    registry = Registry().with_resources(resources)
    targets = {
        "metadata.json": json.loads((entry_dir / "metadata.json").read_text(encoding="utf-8")),
        "manifest.json": json.loads((entry_dir / "manifest.json").read_text(encoding="utf-8")),
        "download.yaml": yaml.safe_load((entry_dir / "download.yaml").read_text(encoding="utf-8")),
        "checksums.json": json.loads((entry_dir / "checksums.json").read_text(encoding="utf-8")),
    }
    for filename, instance in targets.items():
        schema_name = filename.replace(".json", ".schema.json").replace(".yaml", ".schema.json")
        errors = sorted(
            Draft202012Validator(
                schemas[schema_name],
                registry=registry,
                format_checker=FormatChecker(),
            ).iter_errors(instance),
            key=lambda err: err.path,
        )
        assert not errors, [error.message for error in errors]

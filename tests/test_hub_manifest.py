import json
import zipfile

from typer.testing import CliRunner

from mddatanet.cli import app
from mddatanet.convert import convert_package
from mddatanet.hub import export_manifest
from mddatanet.io.checksums import sha256_file
from mddatanet.labels.service import label_package

from tests.helpers import write_tiny_multimodel_pdb


def test_export_manifest_for_valid_zip(tmp_path):
    pdb = write_tiny_multimodel_pdb(tmp_path / "tiny.pdb")
    raw = tmp_path / "raw.mddatanet"
    labeled_zip = tmp_path / "labeled.mddatanet.zip"
    out = tmp_path / "hub_dataset"
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

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    download = (out / "download.yaml").read_text(encoding="utf-8")
    assert (out / "metadata.json").exists()
    assert (out / "dataset_card.md").exists()
    assert (out / "checksums.json").exists()
    assert manifest["dataset_id"] == "tiny_ligand"
    assert manifest["schema_version"] == "1.0"
    assert manifest["package"]["sha256"] == sha256_file(labeled_zip)
    assert manifest["package"]["size_bytes"] == labeled_zip.stat().st_size
    assert manifest["tags"]["task"]["event_family"] == "ligand_unbinding"
    assert manifest["baseline_metrics"]["events"]["ligand_unbinding"]["valid_future_frame_count"] == 1
    assert "TO_BE_PROVIDED" in download
    assert "schema_version: '1.0'" in download
    assert (out / "citation.bib").exists()
    assert (out / "baseline_metrics.json").exists()


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

import json
import zipfile

from typer.testing import CliRunner

from mddatanet.cli import app
from mddatanet.convert import convert_package
from mddatanet.format.metadata import read_metadata
from mddatanet.format.validation import validate_package
from mddatanet.hf.workspace import init_workspace, prepare_workspace, validate_workspace
from mddatanet.io.split_package import split_package_for_hub
from mddatanet.io.zarr_store import open_zarr_group

from tests.helpers import write_ligand_unbinding_pdb, write_tiny_multimodel_pdb


def test_default_convert_writes_compressed_trajectory_layout(tmp_path):
    pdb = write_tiny_multimodel_pdb(tmp_path / "tiny.pdb")
    out = tmp_path / "tiny.mddatanet"

    convert_package(topology=pdb, trajectory=None, coordinates=None, name="tiny", out=out)

    metadata = read_metadata(out)
    zarr_root = open_zarr_group(out / "dataset.zarr", mode="r")
    assert metadata.data_mode == "hybrid"
    assert metadata.storage_profile == "compressed"
    assert metadata.coordinate_storage.included
    assert zarr_root["trajectory"]["positions"].shape == (2, 4, 3)
    assert str(zarr_root["trajectory"]["positions"].dtype) == "float32"
    assert "atom_names" in zarr_root["topology"]
    assert "arrays" not in zarr_root
    assert validate_package(out).ok


def test_full_profile_float64_precision_and_stride(tmp_path):
    pdb = write_ligand_unbinding_pdb(tmp_path / "ligand.pdb")
    out = tmp_path / "full.mddatanet"

    convert_package(
        topology=pdb,
        trajectory=None,
        coordinates=None,
        name="full",
        out=out,
        storage_profile="full",
        coordinate_dtype="float64",
        coordinate_precision=0.5,
        stride=2,
    )

    metadata = read_metadata(out)
    zarr_root = open_zarr_group(out / "dataset.zarr", mode="r")
    assert metadata.storage_profile == "full"
    assert metadata.coordinate_storage.quantized
    assert metadata.sampling.source_frame_count == 4
    assert metadata.sampling.stored_frame_count == 2
    assert str(zarr_root["trajectory"]["positions"].dtype) == "float64"
    assert zarr_root["trajectory"]["source_frame_indices"][:].tolist() == [0, 2]
    assert validate_package(out).ok


def test_linked_storage_omits_positions_and_validates_download_yaml(tmp_path):
    pdb = write_tiny_multimodel_pdb(tmp_path / "tiny.pdb")
    out = tmp_path / "linked.mddatanet"

    convert_package(
        topology=pdb,
        trajectory=None,
        coordinates=None,
        name="linked",
        out=out,
        storage_profile="linked",
        coordinates_url="https://storage.example/traj.zarr.zip",
        coordinates_sha256="abc123",
    )

    metadata = read_metadata(out)
    zarr_root = open_zarr_group(out / "dataset.zarr", mode="r")
    assert metadata.storage_profile == "linked"
    assert not metadata.coordinate_storage.included
    assert "positions" not in zarr_root["trajectory"]
    assert (out / "download.yaml").exists()
    assert validate_package(out).ok


def test_analyze_command_runs_builtin_preset(tmp_path):
    pdb = write_ligand_unbinding_pdb(tmp_path / "ligand.pdb")
    project = tmp_path / "project"
    init_workspace(project)
    prepare_workspace(project_root=project, topology=pdb, keep_solvent=True, overwrite=True)

    result = CliRunner().invoke(
        app,
        [
            "analyze",
            str(project),
            "--preset",
            "ligand_unbinding",
            "--ligand",
            "resname LIG",
            "--pocket",
            "protein",
            "--param",
            "distance_threshold=5.0",
        ],
    )

    assert result.exit_code == 0, result.output
    manifest = json.loads((project / ".mddn_cache" / "mddatanet.json").read_text())
    assert manifest["analysis"]["primary_metric"] == "ligand_pocket_min_distance"
    assert not validate_workspace(project)


def test_split_package_outputs_labels_and_coordinate_archives(tmp_path):
    pdb = write_ligand_unbinding_pdb(tmp_path / "ligand.pdb")
    raw = tmp_path / "raw.mddatanet"
    labels_zip = tmp_path / "dataset.labels.mddatanet.zip"
    coordinates_zip = tmp_path / "dataset.coordinates.zarr.zip"
    convert_package(topology=pdb, trajectory=None, coordinates=None, name="ligand", out=raw)

    out_labels, out_coordinates = split_package_for_hub(
        input_path=raw,
        out_labels=labels_zip,
        out_coordinates=coordinates_zip,
    )

    assert out_labels.exists()
    assert out_coordinates.exists()
    with zipfile.ZipFile(out_coordinates) as archive:
        assert any(name.startswith("trajectory/positions/") for name in archive.namelist())
    with zipfile.ZipFile(out_labels) as archive:
        names = archive.namelist()
        assert any(name.endswith("download.yaml") for name in names)
        assert not any("dataset.zarr/trajectory/positions/" in name for name in names)
    with zipfile.ZipFile(out_labels) as archive:
        metadata_name = next(name for name in archive.namelist() if name.endswith("metadata.json"))
        metadata = json.loads(archive.read(metadata_name))
    assert metadata["storage_profile"] == "linked"

import pytest

from mddatanet import MDDataNetDataset
from mddatanet.convert import convert_package
from mddatanet.labels.service import label_package
from mddatanet.utils.errors import PackageError

from tests.helpers import write_ligand_unbinding_pdb, write_tiny_multimodel_pdb


def _labeled_ligand_package(tmp_path):
    pdb = write_ligand_unbinding_pdb(tmp_path / "ligand.pdb")
    raw = tmp_path / "raw.mddatanet"
    labeled = tmp_path / "labeled.mddatanet"
    convert_package(topology=pdb, trajectory=None, coordinates=None, name="ligand", out=raw)
    label_package(
        input_path=raw,
        out=labeled,
        preset="ligand_unbinding",
        preset_args={"ligand": "resname LIG", "pocket": "resname ALA"},
        param_overrides={"distance_threshold": 5.0, "horizon_frames": 1},
    )
    return labeled


def test_mddatanet_dataset_returns_numpy_window_dict(tmp_path):
    package = _labeled_ligand_package(tmp_path)

    with MDDataNetDataset(package, window_length=2, target="ligand_unbinding_future_1") as dataset:
        assert len(dataset) == 2
        item = dataset[0]

    assert set(item) == {
        "coordinates",
        "label",
        "valid",
        "frame_indices",
        "source_frame_indices",
        "trajectory_ids",
        "run_ids",
        "target",
        "metadata",
    }
    assert item["coordinates"].shape == (2, 4, 3)
    assert item["frame_indices"].tolist() == [0, 1]
    assert item["source_frame_indices"].tolist() == [0, 1]
    assert item["target"] == "ligand_unbinding_future_1"
    assert bool(item["valid"])
    assert item["metadata"]["dataset_name"] == "ligand"


def test_mddatanet_dataset_skips_invalid_tail_frames(tmp_path):
    package = _labeled_ligand_package(tmp_path)

    with MDDataNetDataset(package, window_length=1, target="ligand_unbinding_future_1") as dataset:
        source_frames = [item["source_frame_indices"].tolist()[0] for item in dataset]

    assert source_frames == [0, 1, 2]


def test_mddatanet_dataset_does_not_cross_run_boundaries(tmp_path):
    topology = write_tiny_multimodel_pdb(tmp_path / "topology.pdb")
    run_a = write_tiny_multimodel_pdb(tmp_path / "run_a.pdb")
    run_b = write_tiny_multimodel_pdb(tmp_path / "run_b.pdb")
    raw = tmp_path / "raw.mddatanet"
    labeled = tmp_path / "labeled.mddatanet"
    convert_package(
        topology=topology,
        trajectory=[run_a, run_b],
        coordinates=None,
        name="multi",
        out=raw,
        run_id=["run_a", "run_b"],
    )
    label_package(
        input_path=raw,
        out=labeled,
        preset="ligand_unbinding",
        preset_args={"ligand": "name CA", "pocket": "name N"},
        param_overrides={"distance_threshold": 1.5, "horizon_frames": 0},
    )

    with MDDataNetDataset(labeled, window_length=2, target="ligand_unbinding_future_0") as dataset:
        run_windows = [item["run_ids"].tolist() for item in dataset]

    assert run_windows == [["run_a", "run_a"], ["run_b", "run_b"]]


def test_mddatanet_dataset_requires_embedded_coordinates(tmp_path):
    pdb = write_tiny_multimodel_pdb(tmp_path / "tiny.pdb")
    linked = tmp_path / "linked.mddatanet"
    convert_package(
        topology=pdb,
        trajectory=None,
        coordinates=None,
        name="linked",
        out=linked,
        storage_profile="linked",
        coordinates_url="https://storage.example/traj.zarr.zip",
        coordinates_sha256="abc123",
    )

    with pytest.raises(PackageError, match="embedded trajectory/positions"):
        MDDataNetDataset(linked, window_length=1, target="ligand_unbinding_future_1")


def test_mddatanet_dataset_rejects_non_future_target(tmp_path):
    package = _labeled_ligand_package(tmp_path)

    with pytest.raises(PackageError, match="Unsupported target"):
        MDDataNetDataset(package, window_length=1, target="ligand_unbinding")

import json

from mddatanet.convert import convert_package
from mddatanet.features.compute import featurize_package
from mddatanet.format.metadata import read_metadata
from mddatanet.format.validation import validate_package
from mddatanet.io.zarr_store import open_zarr_group
from mddatanet.labels.service import label_package
from mddatanet.splits.service import split_package

from tests.helpers import write_ligand_unbinding_pdb, write_tiny_pdb_dcd, write_tiny_pdb_xtc


def test_generated_pdb_xtc_workflow(tmp_path):
    pdb, xtc = write_tiny_pdb_xtc(tmp_path)
    raw = tmp_path / "pdb_xtc.mddatanet"
    features = tmp_path / "pdb_xtc_features.mddatanet"
    convert_package(topology=pdb, coordinates=None, trajectory=xtc, name="pdb_xtc", out=raw)
    featurize_package(
        input_path=raw,
        out=features,
        feature_config={
            "features": [
                {
                    "name": "ligand_pocket_distance",
                    "type": "distance",
                    "selection_a": "resname LIG",
                    "selection_b": "resname ALA and name N",
                    "mode": "single_atom",
                }
            ]
        },
    )

    metadata = read_metadata(features)
    assert metadata.system.num_frames == 4
    assert validate_package(features).ok


def test_generated_coordinate_plus_dcd_workflow(tmp_path):
    pdb, dcd = write_tiny_pdb_dcd(tmp_path)
    out = tmp_path / "pdb_coordinates_dcd.mddatanet"

    convert_package(topology=pdb, coordinates=pdb, trajectory=dcd, name="pdb_dcd", out=out)

    assert validate_package(out).ok
    metadata = read_metadata(out)
    assert metadata.system.num_frames == 3
    assert metadata.source.coordinates_file == str(pdb)


def test_generated_multirun_trajectory_split(tmp_path):
    pdb, xtc_a = write_tiny_pdb_xtc(tmp_path / "a")
    _, xtc_b = write_tiny_pdb_xtc(tmp_path / "b")
    raw = tmp_path / "multi.mddatanet"
    ready = tmp_path / "multi_ready.mddatanet"

    convert_package(
        topology=pdb,
        coordinates=None,
        trajectory=[xtc_a, xtc_b],
        run_id=["run_a", "run_b"],
        name="multi",
        out=raw,
    )
    split_package(
        input_path=raw,
        out=ready,
        strategy="trajectory",
        train=0.5,
        val=0.0,
        test=0.5,
    )

    zarr_root = open_zarr_group(ready / "dataset.zarr", mode="r")
    train_runs = {str(zarr_root["trajectory"]["run_ids"][index]) for index in zarr_root["splits"]["train"][:]}
    test_runs = {str(zarr_root["trajectory"]["run_ids"][index]) for index in zarr_root["splits"]["test"][:]}
    assert train_runs.isdisjoint(test_runs)
    assert validate_package(ready).ok


def test_generated_pbc_contact_feature(tmp_path):
    pdb, xtc = write_tiny_pdb_xtc(tmp_path, pbc=True)
    raw = tmp_path / "pbc_raw.mddatanet"
    features = tmp_path / "pbc_features.mddatanet"
    convert_package(topology=pdb, coordinates=None, trajectory=xtc, name="pbc", out=raw)
    featurize_package(
        input_path=raw,
        out=features,
        feature_config={
            "features": [
                {
                    "name": "pbc_contact",
                    "type": "contact",
                    "selection_a": "resname LIG",
                    "selection_b": "resname ALA and name N",
                    "threshold_angstrom": 1.0,
                }
            ]
        },
    )

    zarr_root = open_zarr_group(features / "dataset.zarr", mode="r")
    assert bool(zarr_root["features"]["pbc_contact"][0])
    assert validate_package(features).ok


def test_generated_ligand_unbinding_preset_workflow(tmp_path):
    pdb = write_ligand_unbinding_pdb(tmp_path / "ligand_unbinding.pdb")
    raw = tmp_path / "raw.mddatanet"
    labeled = tmp_path / "labeled.mddatanet"
    convert_package(topology=pdb, coordinates=None, trajectory=None, name="ligand", out=raw)
    label_package(
        input_path=raw,
        out=labeled,
        preset="ligand_unbinding",
        preset_args={"ligand": "resname LIG", "pocket": "resname ALA"},
        param_overrides={"distance_threshold": 5.0, "horizon_frames": 1},
    )

    zarr_root = open_zarr_group(labeled / "dataset.zarr", mode="r")
    event_now = zarr_root["labels"]["ligand_unbinding"]["event_now"][:]
    assert list(event_now) == [False, False, True, True]
    metrics = json.loads((labeled / "baseline_metrics.json").read_text(encoding="utf-8"))
    assert metrics["events"]["ligand_unbinding"]["transition_count"] == 1
    assert validate_package(labeled).ok

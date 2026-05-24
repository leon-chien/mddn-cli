import json

from mddatanet.convert import convert_package
from mddatanet.format.validation import validate_package
from mddatanet.io.zarr_store import open_zarr_group
from mddatanet.labels.service import label_package

from tests.helpers import write_tiny_multimodel_pdb


def test_label_valid_mask_and_metrics_are_written(tmp_path):
    pdb = write_tiny_multimodel_pdb(tmp_path / "tiny.pdb")
    raw = tmp_path / "raw.mddatanet"
    labeled = tmp_path / "labeled.mddatanet"
    convert_package(
        topology=pdb,
        coordinates=None,
        trajectory=[pdb, pdb],
        name="tiny",
        out=raw,
        run_id=["a", "b"],
    )

    events = tmp_path / "events.yaml"
    events.write_text(
        """
events:
  - name: unbound
    type: feature_threshold
    feature: ligand_pocket_min_distance
    operator: greater_than
    threshold: 1.5
    horizon_frames: 1
""",
        encoding="utf-8",
    )
    label_package(
        input_path=raw,
        out=labeled,
        preset="ligand_unbinding",
        preset_args={"ligand": "name CA", "pocket": "name N"},
        param_overrides={"distance_threshold": 1.5, "horizon_frames": 1},
    )

    zarr_root = open_zarr_group(labeled / "dataset.zarr", mode="r")
    group = zarr_root["labels"]["ligand_unbinding"]
    assert list(group["event_future_1_valid"][:]) == [True, False, True, False]
    assert list(group["event_future_1"][:]) == [True, False, True, False]
    assert list(group["time_to_event"][:]) == [1, 0, 1, 0]
    metrics = json.loads((labeled / "baseline_metrics.json").read_text(encoding="utf-8"))
    event_metrics = metrics["events"]["ligand_unbinding"]
    assert event_metrics["valid_future_frame_count"] == 2
    assert event_metrics["valid_future_positive_rate"] == 1.0
    assert validate_package(labeled).ok


def test_validation_catches_corrupted_future_label(tmp_path):
    pdb = write_tiny_multimodel_pdb(tmp_path / "tiny.pdb")
    raw = tmp_path / "raw.mddatanet"
    labeled = tmp_path / "labeled.mddatanet"
    convert_package(topology=pdb, coordinates=None, trajectory=None, name="tiny", out=raw)
    label_package(
        input_path=raw,
        out=labeled,
        preset="ligand_unbinding",
        preset_args={"ligand": "name CA", "pocket": "name N"},
        param_overrides={"distance_threshold": 1.5, "horizon_frames": 1},
    )
    zarr_root = open_zarr_group(labeled / "dataset.zarr", mode="a")
    zarr_root["labels"]["ligand_unbinding"]["event_future_1"][0] = False

    result = validate_package(labeled, check_checksums=False)

    assert not result.ok
    assert any("fixed-horizon semantics" in error for error in result.errors)

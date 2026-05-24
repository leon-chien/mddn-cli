import zarr

from mddatanet.convert import convert_package
from mddatanet.labels.service import label_package

from tests.helpers import write_tiny_multimodel_pdb


def test_preset_label_computes_missing_feature(tmp_path):
    pdb = write_tiny_multimodel_pdb(tmp_path / "tiny.pdb")
    raw = tmp_path / "raw.mddatanet"
    labeled = tmp_path / "labeled.mddatanet"
    convert_package(topology=pdb, trajectory=None, coordinates=None, name="tiny", out=raw, overwrite=True)

    label_package(
        input_path=raw,
        out=labeled,
        preset="ligand_unbinding",
        preset_args={"ligand": "name CA", "pocket": "name N"},
        param_overrides={"distance_threshold": 1.5, "horizon_frames": 1},
        overwrite=True,
    )

    root = zarr.open_group(str(labeled / "dataset.zarr"), mode="r")
    assert "ligand_pocket_min_distance" in root["features"]
    assert root["labels"]["ligand_unbinding"]["event_now"][:].tolist() == [False, True]


import zarr

from mddatanet.io.zarr_store import create_string_array, create_zarr_store


def test_string_array_writer(tmp_path):
    root = create_zarr_store(tmp_path / "store.zarr", overwrite=True)

    create_string_array(root["arrays"], "atom_names", ["N", "CA"])

    reopened = zarr.open_group(str(tmp_path / "store.zarr"), mode="r")
    assert reopened["arrays"]["atom_names"][:].tolist() == ["N", "CA"]


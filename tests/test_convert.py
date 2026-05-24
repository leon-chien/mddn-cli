from mddatanet.convert import convert_package
from mddatanet.format.provenance import read_provenance
from mddatanet.format.validation import validate_package

from tests.helpers import write_tiny_multimodel_pdb


def test_convert_writes_valid_raw_package_and_source_provenance(tmp_path):
    pdb = write_tiny_multimodel_pdb(tmp_path / "tiny.pdb")
    out = tmp_path / "tiny.mddatanet"

    convert_package(topology=pdb, trajectory=None, coordinates=None, name="tiny", out=out, overwrite=True)

    result = validate_package(out)
    provenance = read_provenance(out)
    assert result.ok
    assert provenance.source_files[0].role == "topology"
    assert provenance.source_files[0].size_bytes > 0
    assert provenance.frame_stride == 1


def test_convert_frame_slice_is_stop_exclusive(tmp_path):
    pdb = write_tiny_multimodel_pdb(tmp_path / "tiny.pdb")
    out = tmp_path / "tiny.mddatanet"

    convert_package(
        topology=pdb,
        trajectory=None,
        coordinates=None,
        name="tiny",
        out=out,
        start=1,
        stop=2,
        overwrite=True,
    )

    import zarr

    root = zarr.open_group(str(out / "dataset.zarr"), mode="r")
    assert root["arrays"]["frame_indices"][:].tolist() == [1]


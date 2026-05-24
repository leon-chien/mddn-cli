from pydantic import ValidationError

from mddatanet.format.schema import Metadata, SystemMetadata


def test_metadata_schema_valid():
    metadata = Metadata(
        dataset_name="demo",
        system=SystemMetadata(num_atoms=10, num_residues=2, num_frames=5),
    )

    assert metadata.dataset_name == "demo"
    assert metadata.system.num_frames == 5


def test_metadata_schema_rejects_negative_frames():
    try:
        SystemMetadata(num_atoms=1, num_residues=1, num_frames=-1)
    except ValidationError:
        return
    raise AssertionError("negative frames should be rejected")


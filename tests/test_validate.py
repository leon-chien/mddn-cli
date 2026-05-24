from mddatanet.format.schema import Metadata, SystemMetadata
from mddatanet.format.validation import validate_package
from mddatanet.io.package import create_package_directory


def test_validate_catches_missing_metadata(tmp_path):
    package_dir = tmp_path / "bad.mddatanet"
    package_dir.mkdir()

    result = validate_package(package_dir)

    assert not result.ok
    assert any("metadata.json missing" in error for error in result.errors)


def test_validate_package_created_by_helper(tmp_path):
    metadata = Metadata(
        dataset_name="tiny",
        system=SystemMetadata(num_atoms=1, num_residues=1, num_frames=0),
    )
    package_dir = tmp_path / "tiny.mddatanet"
    create_package_directory(package_dir, metadata=metadata)

    result = validate_package(package_dir)

    assert result.ok


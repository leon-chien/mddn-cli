from mddatanet.format.schema import Metadata, SystemMetadata
from mddatanet.format.validation import inspect_package
from mddatanet.io.package import create_package_directory


def test_inspect_summary(tmp_path):
    metadata = Metadata(
        dataset_name="inspect_me",
        system=SystemMetadata(num_atoms=1, num_residues=1, num_frames=0),
    )
    package_dir = tmp_path / "inspect_me.mddatanet"
    create_package_directory(package_dir, metadata=metadata)

    summary = inspect_package(package_dir)

    assert summary["dataset_name"] == "inspect_me"
    assert summary["validation_ok"] is True

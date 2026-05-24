from mddatanet.format.schema import Metadata, SystemMetadata
from mddatanet.io.package import create_package_directory, pack_package, unpack_package


def test_package_create_pack_unpack(tmp_path):
    metadata = Metadata(
        dataset_name="tiny",
        system=SystemMetadata(num_atoms=1, num_residues=1, num_frames=3),
    )
    package_dir = tmp_path / "tiny.mddatanet"
    create_package_directory(package_dir, metadata=metadata)

    assert (package_dir / "dataset.zarr").exists()
    assert (package_dir / "metadata.json").exists()
    assert (package_dir / "checksums.json").exists()

    package_zip = tmp_path / "tiny.mddatanet.zip"
    pack_package(package_dir, package_zip)
    assert package_zip.exists()

    unpacked = tmp_path / "unpacked"
    unpack_package(package_zip, unpacked)
    assert (unpacked / "tiny.mddatanet" / "metadata.json").exists()


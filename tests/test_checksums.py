from mddatanet.io.checksums import sha256_file, write_checksums


def test_streaming_checksum_and_manifest(tmp_path):
    package_dir = tmp_path / "p.mddatanet"
    package_dir.mkdir()
    payload = package_dir / "payload.bin"
    payload.write_bytes(b"abc" * 1024)

    digest = sha256_file(payload, block_size=128)
    manifest = write_checksums(package_dir)

    assert manifest["payload.bin"] == digest
    assert "checksums.json" not in manifest


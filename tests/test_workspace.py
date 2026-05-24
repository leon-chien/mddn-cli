from mddatanet.io.workspace import copy_file_with_hardlink_fallback


def test_workspace_hardlink_fallback_helper(tmp_path):
    source = tmp_path / "source.txt"
    destination = tmp_path / "nested" / "destination.txt"
    source.write_text("payload", encoding="utf-8")

    copy_file_with_hardlink_fallback(source, destination)

    assert destination.read_text(encoding="utf-8") == "payload"


import re
from pathlib import Path


DOCS = [
    "docs/quickstart.md",
    "docs/command_reference.md",
    "docs/feature_yaml_reference.md",
    "docs/event_yaml_reference.md",
    "docs/preset_guide.md",
    "docs/package_format.md",
    "docs/troubleshooting.md",
    "docs/workflows.md",
    "docs/versioning.md",
    "CHANGELOG.md",
]


def test_documentation_files_exist():
    for path in DOCS:
        assert Path(path).exists(), path


def test_readme_links_point_to_existing_local_docs():
    readme = Path("README.md").read_text(encoding="utf-8")
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", readme)
    local_links = [link for link in links if not link.startswith(("http://", "https://"))]

    assert local_links
    for link in local_links:
        assert Path(link).exists(), link

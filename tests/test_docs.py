import re
from pathlib import Path


DOCS = [
    "docs/quickstart.md",
    "docs/current_cli_status.md",
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


def test_agents_contains_trajectory_learning_positioning():
    guide = Path("AGENTS.md").read_text(encoding="utf-8")

    for heading in (
        "## Core Conceptual Analogy",
        "## Benchmark Task Semantics",
        "## Final Project Positioning",
    ):
        assert heading in guide
    assert "Waymo Open Dataset for molecular dynamics trajectories" in guide
    assert "frames t-W:t -> predict event in t:t+H" in guide
    assert "trajectory_ids" in guide
    assert "source_frame_indices" in guide

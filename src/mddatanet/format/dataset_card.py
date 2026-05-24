"""Dataset card generation."""

from __future__ import annotations

from pathlib import Path

from mddatanet.format.schema import Metadata, Provenance


def render_dataset_card(metadata: Metadata, provenance: Provenance | None = None) -> str:
    """Render a concise dataset card from package metadata."""

    lines = [
        f"# {metadata.dataset_name}",
        "",
        "## Summary",
        metadata.description or "No description provided.",
        "",
        "## System",
        f"- Type: {metadata.system.system_type}",
        f"- Atoms: {metadata.system.num_atoms:,}",
        f"- Residues: {metadata.system.num_residues:,}",
        f"- Frames: {metadata.system.num_frames:,}",
        f"- Runs: {metadata.system.num_runs:,}",
        f"- Timestep: {metadata.system.timestep_ps} ps",
        "",
        "## Source",
        f"- Topology: {metadata.source.topology_file or 'unknown'}",
        f"- Coordinates: {metadata.source.coordinates_file or 'none'}",
        f"- Trajectory: {metadata.source.trajectory_file or ', '.join(metadata.source.trajectory_files) or 'unknown'}",
        "",
        "## Features",
    ]
    if metadata.features.feature_names:
        lines.extend(f"- {name}" for name in metadata.features.feature_names)
    else:
        lines.append("- None yet")

    lines.extend(["", "## Events"])
    if metadata.labels.event_names:
        lines.extend(f"- {name}" for name in metadata.labels.event_names)
    else:
        lines.append("- None yet")

    lines.extend(
        [
            "",
            "## Splits",
            metadata.splits.strategy if metadata.splits and metadata.splits.strategy else "None yet",
            "",
            "## Limitations",
            "Labels are reproducible operational definitions derived from trajectory features.",
            "They should not be treated as universal biological truths.",
            "",
            "## License",
            metadata.license,
            "",
            "## Reproduce",
        ]
    )
    if provenance and provenance.commands:
        lines.extend(f"- `{command.command if hasattr(command, 'command') else command}`" for command in provenance.commands)
    else:
        lines.append("Commands are stored in `provenance.json` when available.")
    lines.append("")
    return "\n".join(lines)


def write_dataset_card(package_dir: str | Path, metadata: Metadata, provenance: Provenance | None = None) -> None:
    path = Path(package_dir) / "dataset_card.md"
    path.write_text(render_dataset_card(metadata, provenance), encoding="utf-8")

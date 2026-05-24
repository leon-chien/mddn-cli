"""Dataset card generation."""

from __future__ import annotations

import json
from pathlib import Path

from mddatanet.format.schema import Metadata, Provenance


def render_dataset_card(
    metadata: Metadata,
    provenance: Provenance | None = None,
    *,
    baseline_metrics: dict | None = None,
) -> str:
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
        "## Trajectory Storage",
        f"- Data mode: {metadata.data_mode}",
        f"- Storage profile: {metadata.storage_profile}",
        f"- Coordinates included: {'yes' if metadata.coordinate_storage.included else 'no'}",
        f"- Coordinate path: {metadata.coordinate_storage.path or 'external or unavailable'}",
        f"- Coordinate dtype: {metadata.coordinate_storage.dtype or 'n/a'}",
        f"- Compression: {metadata.coordinate_storage.compression or 'n/a'}",
        f"- Chunk frames: {metadata.coordinate_storage.chunk_frames or 'n/a'}",
        f"- Chunk atoms: {metadata.coordinate_storage.chunk_atoms or 'n/a'}",
        f"- Stride: {metadata.sampling.stride}",
        f"- Stored/source frames: {metadata.sampling.stored_frame_count}/{metadata.sampling.source_frame_count}",
        f"- Quantized: {'yes' if metadata.coordinate_storage.quantized else 'no'}",
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

    events = (baseline_metrics or {}).get("events", {})
    if events:
        lines.extend(["", "## Label Statistics"])
        for event_name, metrics in events.items():
            lines.append(
                f"- {event_name}: event_now positive rate "
                f"{metrics.get('event_now_positive_rate', 0.0):.3f}; "
                f"valid future positive rate {metrics.get('valid_future_positive_rate', 0.0):.3f}; "
                f"valid future frames {metrics.get('valid_future_frame_count', 0)}; "
                f"transitions {metrics.get('transition_count', 0)}"
            )

    lines.extend(
        [
            "",
            "## Splits",
            metadata.splits.strategy if metadata.splits and metadata.splits.strategy else "None yet",
            "",
            "## Limitations",
            "Labels are reproducible operational definitions derived from trajectory features.",
            "They should not be treated as universal biological truths.",
            "For linked packages, coordinate-based ML models must download the coordinate store listed in `download.yaml`.",
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
    metrics_path = Path(package_dir) / "baseline_metrics.json"
    baseline_metrics = None
    if metrics_path.exists():
        baseline_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    path.write_text(
        render_dataset_card(metadata, provenance, baseline_metrics=baseline_metrics),
        encoding="utf-8",
    )

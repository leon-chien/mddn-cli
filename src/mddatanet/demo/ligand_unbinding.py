"""Runtime-generated Hugging Face-native ligand unbinding demo."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import pyarrow.parquet as pq

from mddatanet.hf.workspace import (
    analyze_workspace,
    init_workspace,
    package_workspace,
    prepare_workspace,
    publish_workspace,
    validate_workspace,
    workspace_summary,
)
from mddatanet.utils.errors import MDDataNetError
from mddatanet.utils.logging import console, print_step, print_success


@dataclass(frozen=True)
class DemoResult:
    project_dir: Path
    parquet_dir: Path
    validation_ok: bool
    event_positive_rate: float
    inspect_text: str


def run_ligand_unbinding_demo(
    *,
    output_dir: Path = Path("outputs"),
    overwrite: bool = True,
) -> DemoResult:
    """Run the end-to-end HF-native ligand unbinding demo with synthetic data."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = output_dir / "_ligand_unbinding_demo_work"
    project_dir = output_dir / "ligand_unbinding_demo_hf"
    parquet_dir = output_dir / "ligand_unbinding_demo_parquet"
    for path in (work_dir, project_dir, parquet_dir):
        if path.exists() and overwrite:
            shutil.rmtree(path)
    work_dir.mkdir(parents=True)
    project_dir.mkdir(parents=True)

    try:
        source_pdb = work_dir / "ligand_unbinding_demo.pdb"
        console.print("MDDataNet Hugging Face ligand unbinding demo")
        console.print("Synthetic trajectory: a ligand moves away from a small protein pocket.")

        print_step(1, 6, "Generating tiny runtime PDB trajectory...")
        _write_demo_pdb(source_pdb)

        print_step(2, 6, "Initializing project descriptor...")
        init_workspace(project_dir, overwrite=True)
        _customize_project(project_dir / "mddatanet.yaml")

        print_step(3, 6, "Preparing per-frame Parquet shards with Ray workers...")
        prepare_workspace(
            project_root=project_dir,
            topology=source_pdb,
            trajectory=None,
            keep_solvent=True,
            chunk_size=2,
            overwrite=True,
        )

        print_step(4, 6, "Applying ligand_unbinding analysis...")
        analyze_workspace(
            project_root=project_dir,
            preset="ligand_unbinding",
            ligand="resname LIG",
            pocket="protein",
            param_overrides={"distance_threshold": 6.0},
        )

        print_step(5, 6, "Packaging train/validation/test and metadata_index splits...")
        package_workspace(project_root=project_dir, hf_repo_link="mddatanet/ligand-unbinding-demo")

        print_step(6, 6, "Validating and materializing a no-network publish dry run...")
        errors = validate_workspace(project_dir)
        if errors:
            raise MDDataNetError("Demo workspace failed validation.", suggestion="; ".join(errors))
        publish_workspace(
            project_root=project_dir,
            repo_id="mddatanet/ligand-unbinding-demo",
            dry_run_out=parquet_dir,
        )
        summary = workspace_summary(project_dir)
        inspect_text = "\n".join(f"{key}: {value}" for key, value in summary.items())
        console.print(inspect_text)
        positive_rate = _event_positive_rate(project_dir)
        console.print("Validation: passed")
        console.print(f"ligand_unbinding event positives: {positive_rate:.1%}")
        print_success(str(project_dir))
        console.print(f"Try: mddatanet publish {project_dir} --repo-id USER/ligand-unbinding-demo")
        return DemoResult(
            project_dir=project_dir,
            parquet_dir=parquet_dir,
            validation_ok=True,
            event_positive_rate=positive_rate,
            inspect_text=inspect_text,
        )
    finally:
        if work_dir.exists():
            shutil.rmtree(work_dir)


def _event_positive_rate(project_dir: Path) -> float:
    data_dir = project_dir / ".mddn_cache" / "data"
    labels: list[str] = []
    for path in sorted(data_dir.glob("*.parquet")):
        table = pq.read_table(path, columns=["event_label"])
        labels.extend(str(value.as_py() or "") for value in table.column("event_label"))
    return sum(1 for label in labels if label) / len(labels) if labels else 0.0


def _customize_project(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace("dataset_name: mddatanet-demo", "dataset_name: ligand_unbinding_demo")
    text = text.replace("protein_name: unknown", "protein_name: synthetic_pocket")
    path.write_text(text, encoding="utf-8")


def _write_demo_pdb(path: Path) -> None:
    ligand_x_values = [2.5, 4.0, 5.5, 8.5, 12.5]
    lines: list[str] = []
    for model_index, ligand_x in enumerate(ligand_x_values, start=1):
        lines.append(f"MODEL     {model_index:4d}")
        lines.extend(
            [
                _atom_line("ATOM", 1, "N", "ALA", "A", 1, 0.0, 0.0, 0.0, "N"),
                _atom_line("ATOM", 2, "CA", "ALA", "A", 1, 1.5, 0.0, 0.0, "C"),
                _atom_line("ATOM", 3, "C", "ALA", "A", 1, 0.0, 1.5, 0.0, "C"),
                _atom_line("ATOM", 4, "O", "ALA", "A", 1, 0.0, 0.0, 1.2, "O"),
                _atom_line("HETATM", 5, "C1", "LIG", "B", 2, ligand_x, 0.0, 0.0, "C"),
            ]
        )
        lines.append("ENDMDL")
    lines.append("END")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _atom_line(
    record: str,
    serial: int,
    name: str,
    resname: str,
    chain: str,
    resid: int,
    x: float,
    y: float,
    z: float,
    element: str,
) -> str:
    return (
        f"{record:<6}{serial:5d} {name:^4s} {resname:>3s} {chain:1s}{resid:4d}"
        f"    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {element:>2s}"
    )

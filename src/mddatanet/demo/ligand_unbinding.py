"""Runtime-generated ligand unbinding demo."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from mddatanet.convert import convert_package
from mddatanet.format.validation import format_inspection, inspect_package, validate_package
from mddatanet.labels.service import label_package
from mddatanet.splits.service import split_package
from mddatanet.utils.errors import MDDataNetError
from mddatanet.utils.logging import console, print_step, print_success


@dataclass(frozen=True)
class DemoResult:
    output_zip: Path
    validation_ok: bool
    event_positive_rate: float
    inspect_text: str


def run_ligand_unbinding_demo(
    *,
    output_dir: Path = Path("outputs"),
    overwrite: bool = True,
) -> DemoResult:
    """Run the end-to-end ligand unbinding demo with synthetic runtime data."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = output_dir / "_ligand_unbinding_demo_work"
    final_zip = output_dir / "ligand_unbinding_demo.mddatanet.zip"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)

    try:
        source_pdb = work_dir / "ligand_unbinding_demo.pdb"
        raw_package = work_dir / "raw.mddatanet"
        labeled_package = work_dir / "labeled.mddatanet"
        ready_package = work_dir / "ready.mddatanet"

        console.print("MDDataNet ligand unbinding demo")
        console.print("Synthetic trajectory: a ligand moves away from a small protein pocket.")
        print_step(1, 6, "Generating tiny runtime PDB trajectory...")
        _write_demo_pdb(source_pdb)

        print_step(2, 6, "Converting raw MD data into an MDDataNet package...")
        convert_package(
            topology=source_pdb,
            trajectory=None,
            coordinates=None,
            name="ligand_unbinding_demo",
            description="Synthetic runtime demo labeled for ligand unbinding.",
            out=raw_package,
            store_positions=True,
            overwrite=True,
            command="mddatanet demo ligand_unbinding",
        )

        print_step(3, 6, "Applying ligand_unbinding preset and generating labels...")
        label_package(
            input_path=raw_package,
            out=labeled_package,
            preset="ligand_unbinding",
            preset_args={"ligand": "resname LIG", "pocket": "protein"},
            param_overrides={"distance_threshold": 6.0, "horizon_frames": 2},
            overwrite=True,
            command="mddatanet demo ligand_unbinding",
        )

        print_step(4, 6, "Creating temporal train/validation/test splits...")
        split_package(
            input_path=labeled_package,
            out=ready_package,
            strategy="temporal",
            train=0.6,
            val=0.2,
            test=0.2,
            gap=0,
            overwrite=True,
        )

        print_step(5, 6, "Packing shareable demo archive...")
        if final_zip.exists() and overwrite:
            final_zip.unlink()
        from mddatanet.io.package import pack_package

        pack_package(ready_package, final_zip, overwrite=overwrite)

        print_step(6, 6, "Validating and inspecting final package...")
        validation = validate_package(final_zip)
        summary = inspect_package(final_zip, include_features=True, include_labels=True, include_splits=True)
        positive_rate = (
            summary.get("label_positive_rates", {})
            .get("ligand_unbinding", {})
            .get("event_now", 0.0)
        )
        inspect_text = format_inspection(summary)
        console.print(inspect_text)
        if not validation.ok:
            raise MDDataNetError(
                "Demo package failed validation.",
                suggestion="Run `mddatanet validate outputs/ligand_unbinding_demo.mddatanet.zip` for details.",
            )
        console.print(f"Validation: passed")
        console.print(f"ligand_unbinding event_now positives: {positive_rate:.1%}")
        print_success(str(final_zip))
        console.print(f"Try: mddatanet inspect {final_zip}")
        return DemoResult(
            output_zip=final_zip,
            validation_ok=validation.ok,
            event_positive_rate=positive_rate,
            inspect_text=inspect_text,
        )
    finally:
        if work_dir.exists():
            shutil.rmtree(work_dir)


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


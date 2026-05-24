from pathlib import Path

import MDAnalysis as mda
import numpy as np


def write_tiny_multimodel_pdb(path: Path) -> Path:
    path.write_text(
        """MODEL        1
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       1.000   0.000   0.000  1.00  0.00           C
ATOM      3  C   ALA A   1       1.000   1.000   0.000  1.00  0.00           C
ATOM      4  O   ALA A   1       1.000   1.000   1.000  1.00  0.00           O
ENDMDL
MODEL        2
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       2.000   0.000   0.000  1.00  0.00           C
ATOM      3  C   ALA A   1       2.000   2.000   0.000  1.00  0.00           C
ATOM      4  O   ALA A   1       2.000   2.000   1.000  1.00  0.00           O
ENDMDL
END
""",
        encoding="utf-8",
    )
    return path


def write_mismatched_pdb(path: Path) -> Path:
    path.write_text(
        """MODEL        1
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       1.000   0.000   0.000  1.00  0.00           C
ATOM      3  C   ALA A   1       1.000   1.000   0.000  1.00  0.00           C
ENDMDL
END
""",
        encoding="utf-8",
    )
    return path


def write_tiny_pdb_xtc(prefix: Path, *, pbc: bool = False) -> tuple[Path, Path]:
    prefix.mkdir(parents=True, exist_ok=True)
    pdb_path = prefix / "tiny.pdb"
    xtc_path = prefix / "tiny.xtc"
    universe = _toy_universe()
    if pbc:
        universe.dimensions = [10.0, 10.0, 10.0, 90.0, 90.0, 90.0]
    universe.atoms.positions = _toy_positions(0, pbc=pbc)
    universe.atoms.write(str(pdb_path))
    with mda.Writer(str(xtc_path), universe.atoms.n_atoms) as writer:
        for frame in range(4):
            universe.atoms.positions = _toy_positions(frame, pbc=pbc)
            if pbc:
                universe.dimensions = [10.0, 10.0, 10.0, 90.0, 90.0, 90.0]
            writer.write(universe)
    return pdb_path, xtc_path


def write_tiny_pdb_dcd(prefix: Path) -> tuple[Path, Path]:
    prefix.mkdir(parents=True, exist_ok=True)
    pdb_path = prefix / "tiny.pdb"
    dcd_path = prefix / "tiny.dcd"
    universe = _toy_universe()
    universe.atoms.positions = _toy_positions(0)
    universe.atoms.write(str(pdb_path))
    with mda.Writer(str(dcd_path), universe.atoms.n_atoms) as writer:
        for frame in range(3):
            universe.atoms.positions = _toy_positions(frame)
            writer.write(universe)
    return pdb_path, dcd_path


def write_ligand_unbinding_pdb(path: Path) -> Path:
    lines: list[str] = []
    serial = 1
    for model, ligand_x in enumerate([2.0, 3.0, 7.0, 10.0], start=1):
        lines.append(f"MODEL     {model:4d}")
        atoms = [
            ("N", "ALA", "A", 1, 0.0, 0.0, 0.0, "N"),
            ("CA", "ALA", "A", 1, 1.0, 0.0, 0.0, "C"),
            ("C", "ALA", "A", 1, 0.0, 1.0, 0.0, "C"),
            ("C1", "LIG", "B", 2, ligand_x, 0.0, 0.0, "C"),
        ]
        for name, resname, chain, resid, x, y, z, element in atoms:
            lines.append(
                f"ATOM  {serial:5d} {name:<4} {resname:>3} {chain}{resid:4d}"
                f"    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {element:>2}"
            )
            serial += 1
        lines.append("ENDMDL")
    lines.append("END")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _toy_universe():
    universe = mda.Universe.empty(
        4,
        n_residues=2,
        atom_resindex=np.array([0, 0, 0, 1]),
        trajectory=True,
    )
    universe.add_TopologyAttr("names", ["N", "CA", "C", "C1"])
    universe.add_TopologyAttr("resnames", ["ALA", "LIG"])
    universe.add_TopologyAttr("resids", [1, 2])
    return universe


def _toy_positions(frame: int, *, pbc: bool = False) -> np.ndarray:
    if pbc:
        ligand_x = 9.6
        pocket_x = 0.4
    else:
        ligand_x = 2.0 + frame
        pocket_x = 0.0
    return np.array(
        [
            [pocket_x, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [ligand_x, 0.0, 0.0],
        ],
        dtype=np.float32,
    )

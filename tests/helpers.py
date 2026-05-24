from pathlib import Path


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

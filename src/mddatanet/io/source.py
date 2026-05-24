"""Source-file provenance helpers."""

from __future__ import annotations

from pathlib import Path

from mddatanet.format.schema import Provenance, SourceFile
from mddatanet.io.checksums import sha256_file
from mddatanet.utils.errors import PackageError


def source_file_record(path: str | Path, *, role: str, run_id: str | None = None) -> SourceFile:
    path = Path(path)
    if not path.exists():
        raise PackageError(f"{role} file does not exist: {path}")
    return SourceFile(
        path=str(path),
        resolved_path=str(path.resolve()),
        role=role,
        run_id=run_id,
        sha256=sha256_file(path),
        size_bytes=path.stat().st_size,
        format=path.suffix.lower().lstrip(".") or None,
    )


def source_path(provenance: Provenance, role: str) -> Path | None:
    for source_file in provenance.source_files:
        if source_file.role == role:
            candidate = Path(source_file.resolved_path or source_file.path)
            if candidate.exists():
                return candidate
            fallback = Path(source_file.path)
            if fallback.exists():
                return fallback
            return candidate
    return None


def require_source_path(provenance: Provenance, role: str) -> Path:
    path = source_path(provenance, role)
    if path is None:
        raise PackageError(
            f"Package provenance does not include a {role} source file.",
            suggestion="Re-run `mddatanet convert` so source files are recorded.",
        )
    if not path.exists():
        raise PackageError(
            f"Recorded {role} source file does not exist: {path}",
            suggestion="Move the source file back or re-run `mddatanet convert --store-positions`.",
        )
    return path

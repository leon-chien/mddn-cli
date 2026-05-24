"""Streaming checksum helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

DEFAULT_BLOCK_SIZE = 1024 * 1024
DEFAULT_EXCLUDES = {"checksums.json"}


def sha256_file(path: str | Path, *, block_size: int = DEFAULT_BLOCK_SIZE) -> str:
    """Return the SHA256 digest for a file without reading it all into memory."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def iter_files(root: str | Path, *, exclude: Iterable[str] = DEFAULT_EXCLUDES) -> Iterable[Path]:
    root = Path(root)
    excluded = set(exclude)
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel in excluded or path.name in excluded:
            continue
        yield path


def build_checksums(root: str | Path, *, exclude: Iterable[str] = DEFAULT_EXCLUDES) -> dict[str, str]:
    root = Path(root)
    return {path.relative_to(root).as_posix(): sha256_file(path) for path in iter_files(root, exclude=exclude)}


def write_checksums(root: str | Path, *, exclude: Iterable[str] = DEFAULT_EXCLUDES) -> dict[str, str]:
    root = Path(root)
    checksums = build_checksums(root, exclude=exclude)
    with (root / "checksums.json").open("w", encoding="utf-8") as handle:
        json.dump(checksums, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return checksums


def read_checksums(root: str | Path) -> dict[str, str]:
    with (Path(root) / "checksums.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def verify_checksums(root: str | Path) -> tuple[bool, list[str]]:
    """Verify checksums and return `(ok, problems)`."""

    root = Path(root)
    expected = read_checksums(root)
    problems: list[str] = []
    for relative_path, expected_digest in expected.items():
        path = root / relative_path
        if not path.exists():
            problems.append(f"missing file listed in checksums: {relative_path}")
            continue
        actual = sha256_file(path)
        if actual != expected_digest:
            problems.append(f"checksum mismatch for {relative_path}")
    return not problems, problems


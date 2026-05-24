"""Path helpers for package inputs and outputs."""

from __future__ import annotations

from pathlib import Path

from mddatanet.utils.errors import PackageError

PACKAGE_DIR_SUFFIX = ".mddatanet"
PACKAGE_ZIP_SUFFIX = ".mddatanet.zip"


def as_path(path: str | Path) -> Path:
    return path if isinstance(path, Path) else Path(path)


def is_package_zip(path: str | Path) -> bool:
    return as_path(path).name.endswith(PACKAGE_ZIP_SUFFIX)


def is_package_dir(path: str | Path) -> bool:
    path = as_path(path)
    return path.is_dir() and path.name.endswith(PACKAGE_DIR_SUFFIX)


def require_exists(path: str | Path, *, label: str = "path") -> Path:
    path = as_path(path)
    if not path.exists():
        raise PackageError(f"{label} does not exist: {path}")
    return path


def ensure_can_write(path: str | Path, *, overwrite: bool = False) -> Path:
    path = as_path(path)
    if path.exists() and not overwrite:
        raise PackageError(
            f"Output already exists: {path}",
            suggestion="Use --overwrite to replace it.",
        )
    return path


def package_stem(path: str | Path) -> str:
    """Return a display stem for `.mddatanet` or `.mddatanet.zip` paths."""

    path = as_path(path)
    name = path.name
    if name.endswith(PACKAGE_ZIP_SUFFIX):
        return name[: -len(PACKAGE_ZIP_SUFFIX)]
    if name.endswith(PACKAGE_DIR_SUFFIX):
        return name[: -len(PACKAGE_DIR_SUFFIX)]
    return path.stem


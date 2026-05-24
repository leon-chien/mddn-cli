"""Safe working-copy helpers for package-mutating commands."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from mddatanet.io.package import copy_package_to, pack_package
from mddatanet.utils.paths import is_package_zip, package_stem


class PackageWorkspace:
    """Create a mutable workspace for package transformations.

    The default behavior copies package files to avoid accidental mutation of
    an input package. A future copy-on-write implementation can hardlink known
    unchanged files, but mutable Zarr stores are deliberately copied today.
    """

    def __init__(self, input_path: Path, out: Path, *, overwrite: bool) -> None:
        self.input_path = input_path
        self.out = out
        self.overwrite = overwrite
        self.tempdir: TemporaryDirectory[str] | None = None
        self.path: Path | None = None

    def __enter__(self) -> Path:
        if is_package_zip(self.out):
            self.tempdir = TemporaryDirectory(prefix="mddatanet-work-")
            self.path = Path(self.tempdir.name) / f"{package_stem(self.out)}.mddatanet"
        else:
            self.path = self.out
        copy_package_to(self.input_path, self.path, overwrite=self.overwrite or self.tempdir is not None)
        return self.path

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self.tempdir is not None:
            self.tempdir.cleanup()

    def finalize(self) -> None:
        if self.path is not None and is_package_zip(self.out):
            pack_package(self.path, self.out, overwrite=self.overwrite)


def copy_file_with_hardlink_fallback(source: Path, destination: Path) -> None:
    """Copy a single file, trying a hardlink first.

    This is intended for future immutable-file workspace optimizations, not for
    mutable package files that may be rewritten in place.
    """

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


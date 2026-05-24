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

    The workspace always uses a temporary directory for processing to ensure
    atomicity. The final result is moved to the target destination only when
    `finalize()` is called.
    """

    def __init__(self, input_path: Path, out: Path, *, overwrite: bool) -> None:
        self.input_path = input_path
        self.out = out
        self.overwrite = overwrite
        self.tempdir: TemporaryDirectory[str] = TemporaryDirectory(prefix="mddatanet-work-")
        self.working_path: Path = Path(self.tempdir.name) / f"{package_stem(self.out)}.mddatanet"
        self._finalized = False

    def __enter__(self) -> Path:
        copy_package_to(self.input_path, self.working_path, overwrite=True)
        return self.working_path

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.tempdir.cleanup()

    def finalize(self) -> None:
        """Move the working copy to the final destination."""
        if self._finalized:
            return
        
        from mddatanet.utils.paths import ensure_can_write
        
        if is_package_zip(self.out):
            ensure_can_write(self.out, overwrite=self.overwrite)
            pack_package(self.working_path, self.out, overwrite=self.overwrite)
        else:
            target_dir = ensure_can_write(self.out, overwrite=self.overwrite)
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.move(str(self.working_path), str(target_dir))
        
        self._finalized = True



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


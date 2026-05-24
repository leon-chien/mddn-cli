"""Temporary workspace helpers."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import TracebackType


class TempPackageDir:
    """Context manager that exposes a pathlib temp directory."""

    def __init__(self, *, prefix: str = "mddatanet-") -> None:
        self._temp = TemporaryDirectory(prefix=prefix)
        self.path = Path(self._temp.name)

    def __enter__(self) -> Path:
        return self.path

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._temp.cleanup()


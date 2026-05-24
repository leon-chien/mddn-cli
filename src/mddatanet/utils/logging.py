"""Rich-backed terminal output helpers."""

from __future__ import annotations

from typing import Any


class _PlainConsole:
    def print(self, *objects: Any, **_: Any) -> None:
        print(*objects)


try:  # pragma: no cover - exercised when rich is installed
    from rich.console import Console
    from rich.table import Table

    console: Any = Console()
except Exception:  # pragma: no cover - keeps source importable in bare envs
    Table = None  # type: ignore[assignment]
    console = _PlainConsole()


def print_step(index: int, total: int, message: str) -> None:
    """Print a numbered progress step."""

    console.print(f"[{index}/{total}] {message}")


def print_success(message: str) -> None:
    """Print a success message."""

    console.print(f"Done: {message}")


def print_error(message: str) -> None:
    """Print an error message."""

    console.print(f"Error: {message}")


"""Custom exceptions with user-facing messages."""

from __future__ import annotations


class MDDataNetError(Exception):
    """Base class for expected MDDataNet failures."""

    suggestion: str | None

    def __init__(self, message: str, *, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.suggestion = suggestion

    def display_message(self) -> str:
        if self.suggestion:
            return f"{self.message}\nSuggestion: {self.suggestion}"
        return self.message


class PackageError(MDDataNetError):
    """Package layout, packing, or unpacking failure."""


class ValidationError(MDDataNetError):
    """Package validation failure."""


class SelectionError(MDDataNetError):
    """MDAnalysis atom selection failure."""


class FeatureError(MDDataNetError):
    """Feature configuration or computation failure."""


class LabelError(MDDataNetError):
    """Event or label generation failure."""


class PresetError(MDDataNetError):
    """Preset loading or resolution failure."""


class DependencyError(MDDataNetError):
    """Missing optional/runtime dependency."""

    def __init__(self, dependency: str, *, purpose: str) -> None:
        super().__init__(
            f"Missing dependency '{dependency}' required for {purpose}.",
            suggestion="Install project dependencies with: python -m pip install -e '.[dev]'",
        )

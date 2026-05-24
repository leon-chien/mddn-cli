"""Base interfaces for chunk-aware feature computation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from mddatanet.format.schema import FeatureDefinition


@dataclass(frozen=True)
class FeatureChunk:
    start: int
    stop: int
    values: Any


class FeatureComputer(ABC):
    """Base class for feature computers.

    Implementations should iterate through trajectory frames or frame chunks and
    yield feature chunks without loading full trajectories into memory.
    """

    feature_type: str

    def __init__(self, definition: FeatureDefinition) -> None:
        self.definition = definition

    @abstractmethod
    def iter_chunks(self, universe: Any, frame_indices: Iterable[int]) -> Iterator[FeatureChunk]:
        """Yield computed feature values for frame chunks."""


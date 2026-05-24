"""Feature computer registry."""

from __future__ import annotations

from collections.abc import Callable

from mddatanet.features.base import FeatureComputer
from mddatanet.format.schema import FeatureDefinition
from mddatanet.utils.errors import FeatureError

FeatureFactory = Callable[[FeatureDefinition], FeatureComputer]


class FeatureRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, FeatureFactory] = {}

    def register(self, feature_type: str, factory: FeatureFactory) -> None:
        self._factories[feature_type] = factory

    def create(self, definition: FeatureDefinition) -> FeatureComputer:
        try:
            factory = self._factories[definition.type]
        except KeyError as exc:
            raise FeatureError(f"Unknown feature type: {definition.type}") from exc
        return factory(definition)

    def names(self) -> list[str]:
        return sorted(self._factories)


registry = FeatureRegistry()


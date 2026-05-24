"""Label/event registry."""

from __future__ import annotations

from collections.abc import Callable

from mddatanet.utils.errors import LabelError

EventEvaluator = Callable[..., object]


class LabelRegistry:
    def __init__(self) -> None:
        self._evaluators: dict[str, EventEvaluator] = {}

    def register(self, event_type: str, evaluator: EventEvaluator) -> None:
        self._evaluators[event_type] = evaluator

    def get(self, event_type: str) -> EventEvaluator:
        try:
            return self._evaluators[event_type]
        except KeyError as exc:
            raise LabelError(f"Unknown event type: {event_type}") from exc

    def names(self) -> list[str]:
        return sorted(self._evaluators)


registry = LabelRegistry()


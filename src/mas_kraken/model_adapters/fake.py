"""Deterministic, network-free scripted model for demos and tests."""

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass, field

from mas_kraken.contracts import Message, ModelResponse, ToolDefinition


@dataclass(slots=True)
class FakeModel:
    """Callable script that records independent snapshots of each request."""

    script: tuple[ModelResponse | Exception, ...]
    calls: list[tuple[list[Message], list[ToolDefinition]]] = field(default_factory=list)
    _position: int = field(default=0, init=False, repr=False)

    def __call__(
        self, messages: list[Message], tools: list[ToolDefinition]
    ) -> ModelResponse:
        self.calls.append((deepcopy(messages), deepcopy(tools)))
        if self._position >= len(self.script):
            raise RuntimeError("Fake model script exhausted.")
        item = self.script[self._position]
        self._position += 1
        if isinstance(item, Exception):
            raise item
        return item


def make_fake_model(script: Sequence[ModelResponse | Exception]) -> FakeModel:
    """Create a scripted model; one item is consumed per call."""
    return FakeModel(tuple(script))

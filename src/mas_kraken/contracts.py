"""Provider-independent data contracts for the synchronous conversation loop.

Messages use the OpenAI Chat Completions shape. Frozen result containers do not
recursively freeze their nested message dictionaries; callers should not mutate
messages returned as part of a result.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, NotRequired, TypedDict, TypeAlias


class FunctionCall(TypedDict):
    """Function name and JSON-encoded arguments supplied by the model."""

    name: str
    arguments: str


class ToolCall(TypedDict):
    """OpenAI-style assistant tool call, retained for the M2 tool loop."""

    id: str
    type: Literal["function"]
    function: FunctionCall


class Message(TypedDict):
    """Canonical Chat Completions message, including future tool fields."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None
    name: NotRequired[str]
    tool_call_id: NotRequired[str]
    tool_calls: NotRequired[list[ToolCall]]


@dataclass(frozen=True, slots=True)
class Usage:
    """Normalized token counts; zero means unavailable or unreported."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True, slots=True)
class ModelResponse:
    """A normalized response from a model callable."""

    text: str | None
    tool_calls: tuple[ToolCall, ...]
    finish_reason: str | None
    usage: Usage


TurnStatus: TypeAlias = Literal["completed", "failed"]


@dataclass(frozen=True, slots=True)
class TurnResult:
    """Outcome of a turn, with a snapshot of its canonical messages."""

    final_response: str
    messages: tuple[Message, ...]
    status: TurnStatus
    error: str | None
    usage: Usage


ToolDefinition: TypeAlias = dict[str, object]
ModelFn: TypeAlias = Callable[[list[Message], list[ToolDefinition]], ModelResponse]

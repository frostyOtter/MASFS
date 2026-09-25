# MASFS — Milestone 1 Source Proposal

**Milestone:** M1 — Sync chatbot walking skeleton  
**Status:** Proposal  
**Depends on:** `MASFS-agile-milestones.md`

For M1, each module should remain small and focused. The `src/` package should contain only chatbot essentials—no tools, persistence, delegation, or async code yet.

```text
src/
└── masfs/
    ├── __init__.py
    ├── __main__.py
    ├── contracts.py
    ├── errors.py
    ├── conversation.py
    ├── repl.py
    ├── log.py
    └── model_adapters/
        ├── __init__.py
        ├── fake.py
        └── openai_compatible.py
```

## `src/masfs/__init__.py`

Defines the package’s public API and version.

It should:

- Have a package docstring.
- Define `__version__`.
- Re-export only the most useful stable interfaces.
- Define `__all__`.

Suggested public exports:

```python
from masfs.contracts import ModelFn, ModelResponse, TurnResult
from masfs.conversation import run_turn
from masfs.model_adapters import make_fake_model, make_openai_model

__version__ = "0.1.0"

__all__ = [
    "ModelFn",
    "ModelResponse",
    "TurnResult",
    "make_fake_model",
    "make_openai_model",
    "run_turn",
]
```

Avoid:

- Initializing logging during import.
- Reading environment variables during import.
- Creating an OpenAI client during import.
- Starting the REPL as an import side effect.

---

## `src/masfs/__main__.py`

Acts as the command-line entry point for:

```bash
python -m masfs
```

It should:

1. Read provider configuration from environment variables.
2. Validate that required values are present.
3. Configure logging explicitly.
4. Create the OpenAI-compatible model callable.
5. Start the synchronous REPL.
6. Convert startup configuration errors into concise terminal messages and a nonzero exit code.

Suggested environment variables:

```text
MASFS_BASE_URL
MASFS_API_KEY
MASFS_MODEL
MASFS_REQUEST_TIMEOUT
MASFS_LOG_LEVEL
```

Suggested structure:

```python
def main() -> int:
    ...


if __name__ == "__main__":
    raise SystemExit(main())
```

Credentials must never be:

- Hard-coded
- Logged
- Included in errors
- Loaded when the package is merely imported

`__main__.py` should only wire components together. Conversation behavior belongs in `conversation.py`, and terminal-loop behavior belongs in `repl.py`.

---

## `src/masfs/contracts.py`

Contains the data contracts shared by the conversation loop and model adapters.

### `Message`

Use an OpenAI Chat Completions-compatible shape.

For M1, messages only need user and assistant text, but the type should permit the canonical fields required by later tool calls without introducing tool execution yet.

A minimal form could be:

```python
from typing import Literal, NotRequired, TypedDict


class Message(TypedDict):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None
    name: NotRequired[str]
    tool_call_id: NotRequired[str]
    tool_calls: NotRequired[list[dict[str, object]]]
```

If strict nested typing remains readable, define `FunctionCall` and `ToolCall` separately instead of using a loose dictionary.

### `Usage`

Tracks normalized token counts:

```python
@dataclass(frozen=True, slots=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
```

The adapter should normalize missing provider usage to zero values or `None`, according to one documented project-wide policy.

### `ModelResponse`

Represents a provider-independent model result:

```python
@dataclass(frozen=True, slots=True)
class ModelResponse:
    text: str | None
    tool_calls: tuple[ToolCall, ...]
    finish_reason: str | None
    usage: Usage
```

Although M1 does not execute tools, `tool_calls` is required by the milestone contract and provider probe.

### `TurnResult`

Represents the complete outcome of `run_turn`:

```python
TurnStatus = Literal["completed", "failed"]


@dataclass(frozen=True, slots=True)
class TurnResult:
    final_response: str
    messages: tuple[Message, ...]
    status: TurnStatus
    error: str | None
    usage: Usage
```

The precise collection type may be `list` instead of `tuple`, but immutable result containers are preferable. If dictionaries remain inside a frozen dataclass, document that “frozen” prevents field reassignment but does not recursively freeze nested values.

### `ModelFn`

Defines the boundary consumed by the conversation loop:

```python
from collections.abc import Callable

ToolDefinition = dict[str, object]
ModelFn = Callable[[list[Message], list[ToolDefinition]], ModelResponse]
```

M1 passes an empty tool-definition list during ordinary chat.

The contracts module should contain:

- Types
- Type aliases
- Frozen data containers

It should not contain:

- Provider SDK imports
- Network operations
- Logging configuration
- Conversation logic

---

## `src/masfs/errors.py`

Contains the project-owned exception hierarchy.

This file should be present so the conversation layer does not depend on OpenAI SDK exception types.

Suggested exceptions:

```python
class MasfsError(Exception):
    """Base exception for expected MASFS failures."""


class ConfigurationError(MasfsError):
    """Raised when required runtime configuration is invalid or missing."""


class ModelError(MasfsError):
    """Normalized model-provider failure."""


class ModelTimeoutError(ModelError):
    """Raised when a model request exceeds its configured timeout."""


class ModelAuthenticationError(ModelError):
    """Raised when provider authentication fails."""


class ModelRateLimitError(ModelError):
    """Raised when the provider rejects a request due to rate limiting."""


class ModelResponseError(ModelError):
    """Raised when a provider response cannot be normalized."""
```

Error messages should be safe to expose to the REPL. They must not contain:

- API keys
- Authorization headers
- Full request objects
- Potentially sensitive provider response bodies

Catch specific SDK exceptions in the provider adapter and chain them:

```python
raise ModelTimeoutError("The model request timed out.") from exc
```

Do not use bare `except:` clauses.

---

## `src/masfs/conversation.py`

Implements the synchronous M1 turn boundary.

The principal function is:

```python
def run_turn(
    history: list[Message],
    user_text: str,
    model: ModelFn,
) -> TurnResult:
    ...
```

It should perform this sequence:

1. Validate or normalize the user input.
2. Append the canonical user message.
3. Deep-copy canonical history into a request-local message list.
4. Call the model with the request copy and an empty tool list.
5. Append the normalized assistant response to canonical history.
6. Return a successful `TurnResult`.

Conceptually:

```text
canonical history
    → append user message
    → deep-copy request messages
    → model(request messages, [])
    → append assistant message
    → return result
```

### Request-copy invariant

The model adapter must not receive the canonical list directly.

A shallow list copy is not sufficient because nested message dictionaries could still be changed. Use a deep copy or an explicit message-copy function:

```python
request_messages = deepcopy(history)
```

After the model call, no request-local mutation may appear in canonical history.

### Successful response

A normal M1 response should:

- Append exactly one assistant boundary.
- Put assistant text in `final_response`.
- Set `status="completed"`.
- Set `error=None`.
- Return provider usage.

If a model unexpectedly returns tool calls during a normal M1 chat, the loop should fail predictably because tool execution is not introduced until M2. It should not silently ignore calls.

### Failed-turn closure

If the model raises a normalized `ModelError`, the function should:

1. Keep the already-appended user message.
2. Append an assistant boundary explaining that the turn failed.
3. Return `status="failed"`.
4. Return a safe error message.
5. Preserve valid user/assistant ordering.

For example, the canonical transcript might end with:

```python
{"role": "user", "content": "Hello"}
{"role": "assistant", "content": "[Model request failed: request timed out]"}
```

This prevents the next user message from being merged conceptually with an unanswered prior turn.

### Exception policy

Expected model errors should become failed `TurnResult` values.

Unexpected programming exceptions should generally not be silently swallowed. Either:

- Let them propagate during development and tests, or
- Log them with traceback and convert them under a clearly documented top-level policy.

The “failed turn is closed” requirement must still be considered when deciding where conversion happens.

This module should not:

- Read environment variables
- Import the OpenAI SDK
- Print to the terminal
- Start the REPL
- Perform persistence
- Execute tools
- Use asyncio

---

## `src/masfs/repl.py`

Implements the synchronous terminal interface.

Suggested public function:

```python
from collections.abc import Callable


def run_repl(
    model: ModelFn,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> int:
    ...
```

Injecting input and output callables makes the REPL easy to test without patching built-ins.

It should:

1. Start with an empty canonical history.
2. Prompt for user input.
3. Recognize `/new`.
4. Recognize `/exit`.
5. Pass ordinary input to `run_turn`.
6. Print the assistant response or safe error.
7. Preserve history between normal turns.
8. Exit cleanly on EOF and keyboard interruption.

### `/new`

`/new` should:

- Replace the current history with a new empty list.
- Confirm that a new conversation has started.
- Make no provider call.

### `/exit`

`/exit` should:

- End the loop.
- Return exit status `0`.
- Make no provider call.

### Empty input

Choose and test an explicit policy. A reasonable policy is to ignore empty or whitespace-only input without calling the provider.

### Testability

Avoid embedding direct `input()` and `print()` calls throughout the implementation. Use the injected callables so tests can supply scripted input and capture output.

The REPL owns terminal presentation, but it should not own provider configuration or model construction.

---

## `src/masfs/log.py`

Provides a small project-owned logging interface backed by Loguru.

The purpose is to stop the rest of the package from becoming tightly coupled to Loguru-specific APIs.

It should provide operations such as:

```python
def configure_logging(level: str = "INFO") -> None:
    ...


def debug(message: str, **context: object) -> None:
    ...


def info(message: str, **context: object) -> None:
    ...


def warning(message: str, **context: object) -> None:
    ...


def error(message: str, **context: object) -> None:
    ...


def exception(message: str, **context: object) -> None:
    ...
```

Alternatively, expose a narrow project-owned protocol or wrapper object.

Requirements:

- Configuration is explicit and idempotent.
- API keys and credentials are never logged.
- The adapter accepts plain Python values.
- Runtime contracts do not contain Loguru objects.
- Importing the module does not unexpectedly reconfigure global logging.

M1 does not yet need `session_id`, `turn_id`, and `task_id`, but the adapter should not prevent contextual logging from being introduced later.

Avoid naming the file `logging.py`, because it can be confused with or accidentally shadow Python’s standard-library `logging` package.

---

# Model adapters

## `src/masfs/model_adapters/__init__.py`

Defines the public API for model construction.

It should re-export:

```python
from masfs.model_adapters.fake import make_fake_model
from masfs.model_adapters.openai_compatible import make_openai_model

__all__ = ["make_fake_model", "make_openai_model"]
```

It should not:

- Construct clients
- Read environment variables
- Make network calls
- Contain provider-specific normalization logic

---

## `src/masfs/model_adapters/fake.py`

Implements a deterministic scripted fake model for all normal tests and demos that do not require a live provider.

Suggested factory:

```python
from collections.abc import Sequence


def make_fake_model(
    script: Sequence[ModelResponse | Exception],
) -> ModelFn:
    ...
```

Each invocation should consume the next scripted item:

- If it is a `ModelResponse`, return it.
- If it is an exception, raise it.
- If the script is exhausted, raise a clear test-oriented error.

The fake may also record calls so tests can verify:

- The number of model requests
- Message order
- Tool definitions passed to the model
- Whether request-local mutation affects canonical history

A useful callable implementation might expose captured calls through a small explicit object, but the milestone says the model boundary is a plain callable. One clean option is:

```python
@dataclass
class FakeModel:
    ...

    def __call__(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> ModelResponse:
        ...
```

The factory can return this callable object as `ModelFn`.

The fake model should be:

- Deterministic
- Synchronous
- Network-free
- Thread-free
- Independent of the OpenAI SDK

It should not contain special cases for individual tests when those cases can be expressed through the script.

---

## `src/masfs/model_adapters/openai_compatible.py`

Adapts a third-party OpenAI-compatible Chat Completions endpoint to `ModelFn`.

Suggested factory:

```python
def make_openai_model(
    base_url: str,
    api_key: str,
    model: str,
    *,
    timeout_s: float = 30.0,
) -> ModelFn:
    ...
```

The factory should:

1. Validate constructor arguments.
2. Create a synchronous `openai.OpenAI` client.
3. Return a closure or callable object matching `ModelFn`.

On each invocation, it should:

1. Copy or serialize the supplied messages without modifying them.
2. Build Chat Completions request arguments.
3. Include tool definitions only when the list is nonempty.
4. Apply the configured request timeout.
5. Call the synchronous provider client.
6. Normalize the first completion choice.
7. Convert assistant text, tool calls, finish reason, and usage into `ModelResponse`.
8. Translate SDK/provider errors into project-owned errors.

### Request behavior

The adapter should use the synchronous client:

```python
from openai import OpenAI
```

It must not use:

- `AsyncOpenAI`
- `asyncio.run`
- Background threads
- Provider calls at factory construction time

### Response normalization

Normalize provider-specific values into stable project contracts:

- Missing content → `None` or a documented empty-string policy
- Missing tool calls → empty tuple
- Missing usage → zero/unknown `Usage`
- Missing finish reason → `None`
- Malformed response → `ModelResponseError`

### Error normalization

Catch specific SDK failures and map them to project errors:

```text
OpenAI timeout             → ModelTimeoutError
Authentication failure     → ModelAuthenticationError
Rate-limit response        → ModelRateLimitError
Connection/API failure     → ModelError
Malformed successful reply → ModelResponseError
```

Preserve the original exception with exception chaining, but expose only a sanitized message.

### Dependency injection

For unit testing, it is useful to accept an optional preconstructed client or client factory. If that makes the public factory noisy, keep it in a private helper:

```python
def _make_openai_model_with_client(
    client: OpenAI,
    model: str,
    timeout_s: float,
) -> ModelFn:
    ...
```

That allows tests to use a fake client without network access or invasive monkeypatching.

---

# Dependency direction

Dependencies should flow inward toward contracts:

```text
__main__.py
    ├── model_adapters/openai_compatible.py
    ├── repl.py
    └── log.py

repl.py
    ├── conversation.py
    └── contracts.py

conversation.py
    ├── contracts.py
    └── errors.py

model_adapters/fake.py
    ├── contracts.py
    └── errors.py

model_adapters/openai_compatible.py
    ├── contracts.py
    └── errors.py
```

`contracts.py` and `errors.py` should not import application modules. This keeps circular dependencies out of the package.

# Features that should not be in `src/` during M1

Do not implement these early:

- Tool registry or tool execution
- Iteration loops
- JSONL session persistence
- Child agents
- Threads or executors
- Lifecycle registries
- Background delegation
- Async hosts
- FastAPI or aiohttp
- Profiles
- Memory
- Structured-output correction

The only M1 accommodation for future tools is the `tool_calls` field in `ModelResponse` and the tool-definition parameter in `ModelFn`. Actual tool handling starts in M2.

"""Synchronous OpenAI-compatible Chat Completions model adapter."""

import math
from copy import deepcopy
from typing import cast

import openai

from mas_kraken.contracts import (
    Message,
    ModelFn,
    ModelResponse,
    ToolCall,
    ToolDefinition,
    Usage,
)
from mas_kraken.errors import (
    ConfigurationError,
    ModelAuthenticationError,
    ModelError,
    ModelRateLimitError,
    ModelResponseError,
    ModelTimeoutError,
)


def make_openai_model(
    base_url: str, api_key: str, model: str, *, timeout_s: float = 30.0
) -> ModelFn:
    """Create a sync model callable; no request is sent until it is called."""
    if not base_url.strip() or not api_key.strip() or not model.strip():
        raise ConfigurationError("Base URL, API key, and model are required.")
    if not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ConfigurationError("Request timeout must be a positive finite number.")
    client = openai.OpenAI(base_url=base_url, api_key=api_key, timeout=timeout_s)
    return _make_openai_model_with_client(client, model, timeout_s)


def _make_openai_model_with_client(
    client: openai.OpenAI, model: str, timeout_s: float
) -> ModelFn:
    """Bind a client separately to allow offline provider-shape tests."""

    def complete(messages: list[Message], tools: list[ToolDefinition]) -> ModelResponse:
        kwargs: dict[str, object] = {
            "model": model,
            "messages": deepcopy(messages),
            "timeout": timeout_s,
        }
        if tools:
            kwargs["tools"] = deepcopy(tools)
        try:
            # Public SDK accepts the Chat Completions request shape; the cast
            # keeps project-owned message/tool types independent of SDK types.
            result = client.chat.completions.create(**cast(dict, kwargs))
        except openai.APITimeoutError as exc:
            raise ModelTimeoutError("The model request timed out.") from exc
        except openai.AuthenticationError as exc:
            raise ModelAuthenticationError("Model authentication failed.") from exc
        except openai.RateLimitError as exc:
            raise ModelRateLimitError("The model provider rate-limited the request.") from exc
        except openai.APIConnectionError as exc:
            raise ModelError("Could not connect to the model provider.") from exc
        except openai.APIError as exc:
            raise ModelError("The model provider rejected the request.") from exc

        try:
            choice = result.choices[0]
            assistant = choice.message
            text = assistant.content
            if text is not None and not isinstance(text, str):
                raise ValueError("Invalid assistant content")
            raw_calls = assistant.tool_calls or []
            calls: list[ToolCall] = []
            for call in raw_calls:
                if (
                    not isinstance(call.id, str)
                    or not call.id
                    or call.type != "function"
                    or not isinstance(call.function.name, str)
                    or not call.function.name
                    or not isinstance(call.function.arguments, str)
                ):
                    raise ValueError("Invalid tool call")
                calls.append(
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                )
            if text is None and not calls:
                raise ValueError("Missing assistant reply")
            raw_usage = result.usage
            usage = (
                Usage(
                    prompt_tokens=raw_usage.prompt_tokens,
                    completion_tokens=raw_usage.completion_tokens,
                    total_tokens=raw_usage.total_tokens,
                )
                if raw_usage is not None
                else Usage()
            )
            return ModelResponse(
                text=text,
                tool_calls=tuple(calls),
                finish_reason=choice.finish_reason,
                usage=usage,
            )
        except (AttributeError, IndexError, TypeError, ValueError) as exc:
            raise ModelResponseError("The model returned an unusable response.") from exc

    return complete

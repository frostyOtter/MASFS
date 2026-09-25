"""Offline Chat Completions adapter checks using a stubbed synchronous client."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

openai = pytest.importorskip("openai")
httpx = pytest.importorskip("httpx")

from mas_kraken.errors import (  # noqa: E402
    ConfigurationError,
    ModelAuthenticationError,
    ModelError,
    ModelRateLimitError,
    ModelResponseError,
    ModelTimeoutError,
)
from mas_kraken.model_adapters import make_openai_model  # noqa: E402


def completion(*, content="hello", tool_calls=None, usage=None, choices=True):
    choice = SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=tool_calls),
        finish_reason="stop" if not tool_calls else "tool_calls",
    )
    return SimpleNamespace(choices=[choice] if choices else [], usage=usage)


def client_returning(value=None, *, error=None):
    create = Mock(side_effect=error) if error else Mock(return_value=value)
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def build_model(monkeypatch, client, *, timeout_s=12.5):
    monkeypatch.setattr(openai, "OpenAI", Mock(return_value=client))
    return make_openai_model("https://example.invalid/v1", "secret", "example-model", timeout_s=timeout_s)


def test_text_completion_preserves_messages_and_normalizes_usage(monkeypatch):
    usage = SimpleNamespace(prompt_tokens=4, completion_tokens=2, total_tokens=6)
    client = client_returning(completion(usage=usage))
    model = build_model(monkeypatch, client)
    messages = [{"role": "user", "content": "hi"}]
    original = deepcopy(messages)

    result = model(messages, [])

    assert result.text == "hello"
    assert result.tool_calls == ()
    assert result.finish_reason == "stop"
    assert result.usage.prompt_tokens == 4
    assert result.usage.completion_tokens == 2
    assert result.usage.total_tokens == 6
    assert messages == original
    arguments = client.chat.completions.create.call_args.kwargs
    assert arguments["model"] == "example-model"
    assert arguments["timeout"] == 12.5
    assert arguments["messages"] == original
    assert "tools" not in arguments


def test_missing_usage_has_zero_counts(monkeypatch):
    result = build_model(monkeypatch, client_returning(completion()))([], [])

    assert result.usage.prompt_tokens == 0
    assert result.usage.completion_tokens == 0
    assert result.usage.total_tokens == 0


def test_tool_calls_are_normalized_and_only_sent_when_available(monkeypatch):
    tool_call = SimpleNamespace(
        id="call-1", type="function",
        function=SimpleNamespace(name="calculator", arguments='{"x": 2}'),
    )
    client = client_returning(completion(content=None, tool_calls=[tool_call]))
    definitions = [{"type": "function", "function": {"name": "calculator"}}]

    result = build_model(monkeypatch, client)([{"role": "user", "content": "calculate"}], definitions)

    assert result.text is None
    assert result.finish_reason == "tool_calls"
    assert result.tool_calls == ({
        "id": "call-1", "type": "function",
        "function": {"name": "calculator", "arguments": '{"x": 2}'},
    },)
    assert client.chat.completions.create.call_args.kwargs["tools"] == definitions


@pytest.mark.parametrize("value", ["", "  "])
def test_blank_constructor_fields_are_rejected(value):
    with pytest.raises(ConfigurationError):
        make_openai_model(value, "secret", "model")


def test_empty_choices_are_rejected(monkeypatch):
    model = build_model(monkeypatch, client_returning(completion(choices=False)))

    with pytest.raises(ModelResponseError):
        model([{"role": "user", "content": "hello"}], [])


@pytest.mark.parametrize(
    ("error_factory", "expected"),
    [
        (lambda: openai.APITimeoutError(request=httpx.Request("POST", "https://example.invalid")), ModelTimeoutError),
        (lambda: openai.APIConnectionError(request=httpx.Request("POST", "https://example.invalid")), ModelError),
        (lambda: openai.AuthenticationError("denied", response=httpx.Response(401, request=httpx.Request("POST", "https://example.invalid")), body=None), ModelAuthenticationError),
        (lambda: openai.RateLimitError("limited", response=httpx.Response(429, request=httpx.Request("POST", "https://example.invalid")), body=None), ModelRateLimitError),
    ],
)
def test_sdk_errors_are_normalized_without_leaking_credentials(monkeypatch, error_factory, expected):
    model = build_model(monkeypatch, client_returning(error=error_factory()))

    with pytest.raises(expected) as caught:
        model([{"role": "user", "content": "hello"}], [])

    assert "secret" not in str(caught.value)
    assert caught.value.__cause__ is not None

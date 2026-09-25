"""M1 turn contracts: ordered history, isolation, usage, and failure closure."""

from copy import deepcopy

import pytest

from mas_kraken.contracts import ModelResponse, Usage
from mas_kraken.conversation import run_turn
from mas_kraken.errors import ModelError, ModelTimeoutError
from mas_kraken.model_adapters import make_fake_model


def response(text: str, usage: Usage | None = None) -> ModelResponse:
    return ModelResponse(
        text=text,
        tool_calls=(),
        finish_reason="stop",
        usage=usage or Usage(),
    )


def test_five_turns_preserve_message_order_and_prior_context():
    history = []
    requests = []

    def model(messages, tools):
        requests.append(deepcopy(messages))
        assert tools == []
        return response(f"answer {len(requests)}")

    for number in range(1, 6):
        result = run_turn(history, f"question {number}", model)
        assert result.status == "completed"
        assert result.final_response == f"answer {number}"
        assert result.error is None
        assert len(result.messages) == number * 2
        assert requests[-1] == history[:-1]

    assert [item["role"] for item in history] == ["user", "assistant"] * 5
    assert [item["content"] for item in history] == [
        value
        for number in range(1, 6)
        for value in (f"question {number}", f"answer {number}")
    ]


def test_request_mutation_does_not_change_canonical_history():
    history = [{"role": "assistant", "content": "previous", "tool_calls": [{"id": "original"}]}]

    def model(messages, tools):
        messages[0]["content"] = "overwritten"
        messages[0]["tool_calls"][0]["id"] = "overwritten"
        messages.append({"role": "system", "content": "request only"})
        return response("done")

    result = run_turn(history, "next", model)

    assert history == [
        {"role": "assistant", "content": "previous", "tool_calls": [{"id": "original"}]},
        {"role": "user", "content": "next"},
        {"role": "assistant", "content": "done"},
    ]
    assert list(result.messages) == history


def test_success_returns_provider_usage():
    usage = Usage(prompt_tokens=3, completion_tokens=2, total_tokens=5)

    result = run_turn([], "hello", make_fake_model([response("hi", usage)]))

    assert result.usage == usage


@pytest.mark.parametrize("failure", [ModelError("Unavailable"), ModelTimeoutError("Timed out")])
def test_provider_failure_closes_turn_and_allows_next_turn(failure):
    history = []
    model = make_fake_model([failure, response("recovered")])

    failed = run_turn(history, "first", model)
    assert failed.status == "failed"
    assert failed.error
    assert [message["role"] for message in history] == ["user", "assistant"]
    assert history[-1]["content"]

    succeeded = run_turn(history, "second", model)
    assert succeeded.status == "completed"
    assert [message["role"] for message in history] == [
        "user", "assistant", "user", "assistant"
    ]
    assert history[-1]["content"] == "recovered"


def test_tool_calls_without_tool_support_fail_predictably():
    model = make_fake_model([
        ModelResponse(
            text=None,
            tool_calls=({"id": "call-1", "type": "function", "function": {"name": "x", "arguments": "{}"}},),
            finish_reason="tool_calls",
            usage=Usage(),
        )
    ])
    history = []

    result = run_turn(history, "do it", model)

    assert result.status == "failed"
    assert result.error
    assert [message["role"] for message in history] == ["user", "assistant"]
    assert len(history) == 2


def test_unexpected_programming_error_is_not_silently_converted():
    def broken(messages, tools):
        raise RuntimeError("bug")

    with pytest.raises(RuntimeError, match="bug"):
        run_turn([], "hello", broken)

"""An offline, end-to-end M1 terminal conversation."""

from mas_kraken.contracts import ModelResponse, Usage
from mas_kraken.model_adapters import make_fake_model
from mas_kraken.repl import run_repl


def test_five_reply_session_resets_without_network_access():
    model = make_fake_model([
        ModelResponse(f"answer {number}", (), "stop", Usage())
        for number in range(1, 7)
    ])
    inputs = iter([*(f"question {number}" for number in range(1, 6)), "/new", "fresh", "/exit"])
    output = []
    requests = []

    def recording_model(messages, tools):
        requests.append([message.copy() for message in messages])
        return model(messages, tools)

    status = run_repl(recording_model, input_fn=lambda prompt: next(inputs), output_fn=output.append)

    assert status == 0
    for number in range(1, 7):
        assert any(f"answer {number}" in line for line in output)
    assert len(requests) == 6
    assert [message["content"] for message in requests[4]] == [
        value
        for number in range(1, 5)
        for value in (f"question {number}", f"answer {number}")
    ] + ["question 5"]
    assert [message["content"] for message in requests[5]] == ["fresh"]

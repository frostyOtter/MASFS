"""M1 terminal behavior without real input, output, or network calls."""

from mas_kraken.contracts import ModelResponse, Usage
from mas_kraken.repl import run_repl


def scripted_input(*items):
    iterator = iter(items)
    return lambda prompt: next(iterator)


def test_multiple_inputs_share_context_until_new_command():
    requests = []
    output = []

    def model(messages, tools):
        requests.append([message["content"] for message in messages])
        return ModelResponse(f"reply {len(requests)}", (), "stop", Usage())

    status = run_repl(
        model,
        input_fn=scripted_input("one", "two", "/new", "three", "/exit"),
        output_fn=output.append,
    )

    assert status == 0
    assert requests == [["one"], ["one", "reply 1", "two"], ["three"]]
    assert any("reply 3" in line for line in output)


def test_commands_and_blank_input_do_not_call_model():
    calls = []

    def model(messages, tools):
        calls.append(messages)
        raise AssertionError("No model call expected")

    status = run_repl(
        model,
        input_fn=scripted_input("", "  ", "/new", "/exit"),
        output_fn=lambda text: None,
    )

    assert status == 0
    assert calls == []


def test_end_of_input_exits_cleanly():
    def end_of_input(prompt):
        raise EOFError

    assert run_repl(lambda messages, tools: None, input_fn=end_of_input) == 0


def test_keyboard_interrupt_exits_cleanly():
    def interrupted(prompt):
        raise KeyboardInterrupt

    assert run_repl(lambda messages, tools: None, input_fn=interrupted) == 0

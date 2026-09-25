"""Synchronous terminal interface for the M1 conversation loop."""

from collections.abc import Callable

from mas_kraken.contracts import Message, ModelFn
from mas_kraken.conversation import run_turn


def run_repl(
    model: ModelFn,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> int:
    """Chat until /exit, EOF, or Ctrl-C; /new resets the conversation."""
    history: list[Message] = []
    while True:
        try:
            user_text = input_fn("You: ")
        except (EOFError, KeyboardInterrupt):
            return 0

        command = user_text.strip()
        if command == "/exit":
            return 0
        if command == "/new":
            history = []
            output_fn("New conversation started.")
            continue
        if not command:
            continue

        result = run_turn(history, user_text, model)
        output_fn(f"Assistant: {result.final_response}")
        output_fn("--- " * 5)

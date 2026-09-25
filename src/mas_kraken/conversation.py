"""Synchronous M1 conversation turn boundary."""

from copy import deepcopy

from mas_kraken.contracts import Message, ModelFn, TurnResult, Usage
from mas_kraken.errors import ModelError, ModelResponseError


def run_turn(history: list[Message], user_text: str, model: ModelFn) -> TurnResult:
    """Append one user turn and close it with one assistant message.

    The model receives a deep request copy, never the canonical history. Expected
    model failures return a failed result; unexpected exceptions close the turn
    before propagating so later turns cannot inherit an unanswered user message.
    """
    if not user_text.strip():
        raise ValueError("User message must not be empty.")

    history.append({"role": "user", "content": user_text})
    try:
        response = model(deepcopy(history), [])
        if response.tool_calls:
            raise ModelResponseError("Tool calls are not supported in M1.")
        if response.text is None:
            raise ModelResponseError("The model returned no assistant text.")
    except ModelError as exc:
        error = str(exc) or "The model request failed."
        final_response = f"[Model request failed: {error}]"
        status = "failed"
        usage = Usage()
    except Exception:
        history.append({"role": "assistant", "content": "[Model request failed.]"})
        raise
    else:
        final_response = response.text
        error = None
        status = "completed"
        usage = response.usage

    history.append({"role": "assistant", "content": final_response})
    return TurnResult(
        final_response=final_response,
        messages=tuple(deepcopy(history)),
        status=status,
        error=error if status == "failed" else None,
        usage=usage,
    )

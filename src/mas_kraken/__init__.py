"""MAS Kraken: a small synchronous agent-learning project."""

from mas_kraken.contracts import ModelFn, ModelResponse, TurnResult
from mas_kraken.conversation import run_turn
from mas_kraken.model_adapters import make_fake_model, make_openai_model

__version__ = "0.1.0"

__all__ = [
    "ModelFn",
    "ModelResponse",
    "TurnResult",
    "make_fake_model",
    "make_openai_model",
    "run_turn",
]


def main() -> int:
    """Console-script compatibility wrapper for the package entry point."""
    from mas_kraken.__main__ import main as cli_main

    return cli_main()

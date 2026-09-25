"""Factories for synchronous model callables."""

from mas_kraken.model_adapters.fake import make_fake_model
from mas_kraken.model_adapters.openai_compatible import make_openai_model

__all__ = ["make_fake_model", "make_openai_model"]

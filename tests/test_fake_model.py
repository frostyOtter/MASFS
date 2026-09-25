"""Offline scripted model contract."""

import pytest

from mas_kraken.contracts import ModelResponse, Usage
from mas_kraken.errors import ModelError
from mas_kraken.model_adapters import make_fake_model


def test_scripted_responses_are_returned_in_order():
    first = ModelResponse("one", (), "stop", Usage())
    second = ModelResponse("two", (), "stop", Usage())
    model = make_fake_model([first, second])

    assert model([], []) == first
    assert model([], []) == second


def test_scripted_error_is_raised_without_consuming_next_response():
    answer = ModelResponse("after error", (), "stop", Usage())
    model = make_fake_model([ModelError("offline"), answer])

    with pytest.raises(ModelError, match="offline"):
        model([], [])
    assert model([], []) == answer


def test_exhausted_script_raises_clear_error():
    model = make_fake_model([])

    with pytest.raises(Exception, match="(?i)(exhaust|script)"):
        model([], [])

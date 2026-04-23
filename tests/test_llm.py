"""Tests for the Gemini wrapper. We never hit the network — we fake the
underlying model and exercise the parse / retry / throttle logic.
"""

from __future__ import annotations

import pytest

from src import llm
from src.llm import GeminiClient, LLMError, _parse_json


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _FakeModel:
    def __init__(self, responses: list):
        self.responses = list(responses)
        self.calls = 0

    def generate_content(self, prompt: str):  # noqa: ARG002
        self.calls += 1
        payload = self.responses.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return _FakeResponse(payload)


def _client_with(model: _FakeModel, **kwargs) -> GeminiClient:
    c = GeminiClient(api_key="test", min_spacing_s=0.0, **kwargs)
    c._model = model
    return c


def test_parse_json_strips_fences():
    assert _parse_json("```json\n{\"a\": 1}\n```") == {"a": 1}
    assert _parse_json('{"a": 2}') == {"a": 2}


def test_parse_json_handles_surrounding_prose():
    text = "Here you go:\n```json\n{\"score\": 0.8}\n```\nHope that helps!"
    assert _parse_json(text) == {"score": 0.8}


def test_parse_json_raises_on_garbage():
    with pytest.raises(LLMError):
        _parse_json("not json at all, sorry")


def test_generate_json_happy_path():
    c = _client_with(_FakeModel(['{"fit_score": 0.9}']))
    assert c.generate_json("hi") == {"fit_score": 0.9}


def test_generate_json_retries_on_429(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    model = _FakeModel([RuntimeError("429 resource exhausted"), '{"fit_score": 0.5}'])
    c = _client_with(model)
    assert c.generate_json("hi") == {"fit_score": 0.5}
    assert model.calls == 2


def test_generate_json_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    model = _FakeModel([RuntimeError("503 unavailable")] * 5)
    c = _client_with(model, max_retries=3)
    with pytest.raises(LLMError):
        c.generate_json("hi")
    assert model.calls == 3


def test_generate_json_no_retry_on_non_retryable(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    model = _FakeModel([RuntimeError("400 bad request: prompt violates policy")])
    c = _client_with(model)
    with pytest.raises(LLMError):
        c.generate_json("hi")
    assert model.calls == 1


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(LLMError):
        GeminiClient()

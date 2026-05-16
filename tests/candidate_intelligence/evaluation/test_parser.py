import json

import pytest

from src.candidate_intelligence.evaluation.parser import call_with_retry, parse_evaluation_json


def test_parse_strips_json_fence():
    raw = '```json\n{"summary": "x"}\n```'
    assert parse_evaluation_json(raw) == {"summary": "x"}


def test_parse_strips_bare_fence():
    raw = '```\n{"summary": "x"}\n```'
    assert parse_evaluation_json(raw) == {"summary": "x"}


def test_parse_raises_on_bad_json():
    with pytest.raises((json.JSONDecodeError, ValueError)):
        parse_evaluation_json("not json")


class _Provider:
    name = "fake"
    model = "fake-model"

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def generate(self, prompt, system=None):
        self.calls.append((prompt, system))
        return self._responses.pop(0)


def test_call_with_retry_succeeds_first_try():
    p = _Provider(['{"summary": "x"}'])
    parsed, raw = call_with_retry(p, "prompt", "sys")
    assert parsed == {"summary": "x"}
    assert raw == '{"summary": "x"}'
    assert len(p.calls) == 1


def test_call_with_retry_retries_on_bad_json():
    p = _Provider(["bad", '{"summary": "x"}'])
    parsed, _ = call_with_retry(p, "prompt", "sys")
    assert parsed == {"summary": "x"}
    assert len(p.calls) == 2
    assert "Return ONLY valid JSON" in p.calls[1][0]

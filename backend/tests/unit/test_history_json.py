import json

import httpx
import pytest

from server.ai.agents.history_composer import HistoryComposer
from server.ai.llm.base import LLMResult
from server.ai.llm.providers import GroqProvider, ProviderError


def test_composer_requests_json_and_repairs_an_empty_result():
    class Gateway:
        calls = 0
        def generate(self, *args, **kwargs):
            pytest.fail("La llamada estructurada debe usar generate_json")
        def generate_json(self, messages, *, temperature):
            self.calls += 1
            return LLMResult("" if self.calls == 1 else json.dumps({"datos": []}), "fake", "fake", 10, 5)
    gateway = Gateway()
    result, usage = HistoryComposer(gateway).call("generar", {"claves_solicitadas": []})
    assert result == {"datos": []} and gateway.calls == 2
    assert usage.input_tokens == 20 and usage.output_tokens == 10


def test_groq_json_mode_has_a_completion_budget_and_low_reasoning(monkeypatch):
    def post(url, *, headers, json, timeout):
        assert json["response_format"] == {"type": "json_object"}
        assert json["max_completion_tokens"] == 4096
        assert json["reasoning_effort"] == "low"
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"datos":[]}'}}]})
    monkeypatch.setattr(httpx, "post", post)
    provider = GroqProvider(name="test", api_key="fake", model="openai/gpt-oss-20b",
                            base_url="https://example.test", timeout=2)
    assert provider.generate_json([{ "role": "user", "content": "JSON"}]).text == '{"datos":[]}'


@pytest.mark.parametrize("content", ["", None, "   "])
def test_empty_groq_content_is_a_retryable_error(monkeypatch, content):
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: httpx.Response(
        200, json={"choices": [{"message": {"content": content}}]}))
    provider = GroqProvider(name="test", api_key="fake", model="model",
                            base_url="https://example.test", timeout=2)
    with pytest.raises(ProviderError) as exc:
        provider.generate([])
    assert exc.value.retryable

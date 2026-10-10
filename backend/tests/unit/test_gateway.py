from server.ai.llm.base import LLMResult
from server.ai.llm.gateway import LLMGateway
from server.ai.llm.providers import ProviderError


class Failing:
    name = "a"
    model = "m"

    def generate(self, messages, *, temperature=0.0):
        raise ProviderError("429", retryable=True)


class Backup:
    name = "b"
    model = "m"

    def generate(self, messages, *, temperature=0.0):
        return LLMResult(text="ok", provider=self.name, model=self.model)


def test_gateway_fallback_after_retryable_failure():
    result = LLMGateway([Failing(), Backup()], cooldown_seconds=30).generate(
        [{"role": "user", "content": "hola"}]
    )
    assert result.text == "ok"
    assert result.provider == "b"
    assert result.fallback_used is True

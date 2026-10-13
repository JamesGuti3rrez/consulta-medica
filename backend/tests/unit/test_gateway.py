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


class Rejected:
    name = "rechazada"
    model = "m"

    def __init__(self):
        self.calls = 0

    def generate(self, messages, *, temperature=0.0):
        self.calls += 1
        raise ProviderError("401 Invalid API Key", invalid_credential=True)


def test_rejected_key_is_skipped_and_set_aside():
    rejected = Rejected()
    gateway = LLMGateway([rejected, Backup()], cooldown_seconds=30)
    assert gateway.generate([{"role": "user", "content": "hola"}]).provider == "b"
    gateway.generate([{"role": "user", "content": "hola"}])
    assert rejected.calls == 1
    assert [p["available"] for p in gateway.status()] == [False, True]


def test_all_keys_rejected_raises_llm_unavailable():
    import pytest

    from server.ai.llm.gateway import LLMUnavailable

    with pytest.raises(LLMUnavailable):
        LLMGateway([Rejected(), Rejected()]).generate([{"role": "user", "content": "hola"}])

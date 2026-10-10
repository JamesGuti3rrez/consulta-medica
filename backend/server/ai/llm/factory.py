from server.config import settings
from server.ai.llm.gateway import LLMGateway
from server.ai.llm.providers import GroqProvider, LocalDevelopmentProvider


def build_gateway() -> LLMGateway:
    if not settings.groq_api_keys:
        return LLMGateway([LocalDevelopmentProvider()], cooldown_seconds=settings.provider_cooldown_seconds)

    providers = [
        GroqProvider(
            name=f"groq-{index + 1}",
            api_key=key,
            model=settings.groq_model,
            base_url=settings.groq_base_url,
            timeout=settings.llm_timeout_seconds,
        )
        for index, key in enumerate(settings.groq_api_keys)
    ]
    return LLMGateway(providers, cooldown_seconds=settings.provider_cooldown_seconds)

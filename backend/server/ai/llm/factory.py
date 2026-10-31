from server.config import settings
from server.ai.llm.gateway import LLMGateway
from server.ai.llm.providers import GroqProvider, LocalDevelopmentProvider


def build_gateway(*, config=None) -> LLMGateway:
    config = config or settings
    if not config.groq_api_keys:
        return LLMGateway([LocalDevelopmentProvider()], cooldown_seconds=config.provider_cooldown_seconds)

    providers = [
        GroqProvider(
            name=f"groq-{index + 1}",
            api_key=key,
            model=config.groq_model,
            base_url=config.groq_base_url,
            timeout=config.llm_timeout_seconds,
        )
        for index, key in enumerate(config.groq_api_keys)
    ]
    return LLMGateway(providers, cooldown_seconds=config.provider_cooldown_seconds)

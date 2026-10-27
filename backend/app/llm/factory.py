from app.core.config import settings
from app.llm.base import LLMProvider, LLMProviderNotConfiguredError
from app.llm.openai_compatible import OpenAICompatibleProvider

_PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-20b"),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
}


def create_llm_provider() -> LLMProvider:
    name = settings.LLM_PROVIDER
    api_key = settings.GROQ_API_KEY if name == "groq" else settings.OPENAI_API_KEY
    if not api_key:
        raise LLMProviderNotConfiguredError(
            f"API key for LLM provider '{name}' is not configured"
        )

    base_url, default_model = _PROVIDERS[name]
    return OpenAICompatibleProvider(
        name=name,
        base_url=base_url,
        api_key=api_key,
        model=settings.LLM_MODEL or default_model,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
    )

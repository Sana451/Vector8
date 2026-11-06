from app.core.config import settings
from app.llm.base import LLMProvider, LLMProviderNotConfiguredError
from app.llm.fallback import FallbackLLMProvider
from app.llm.openai_compatible import OpenAICompatibleProvider

_PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-20b"),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "sambanova": ("https://api.sambanova.ai/v1", "gemma-4-31B-it"),
}


def _build_provider(name: str) -> OpenAICompatibleProvider:
    api_key, model = {
        "groq": (settings.GROQ_API_KEY, settings.LLM_GROQ_MODEL),
        "openai": (settings.OPENAI_API_KEY, settings.LLM_OPENAI_MODEL),
        "sambanova": (settings.SAMBANOVA_API_KEY, settings.LLM_SAMBANOVA_MODEL),
    }[name]
    if not api_key:
        raise LLMProviderNotConfiguredError(
            f"API key for LLM provider '{name}' is not configured"
        )

    base_url, default_model = _PROVIDERS[name]
    return OpenAICompatibleProvider(
        name=name,
        base_url=base_url,
        api_key=api_key,
        model=model or default_model,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
    )


def create_llm_provider() -> LLMProvider:
    primary = _build_provider(settings.LLM_PROVIDER)

    fallback_name = settings.LLM_FALLBACK_PROVIDER
    if fallback_name is None or fallback_name == settings.LLM_PROVIDER:
        return primary
    try:
        fallback = _build_provider(fallback_name)
    except LLMProviderNotConfiguredError:
        return primary
    return FallbackLLMProvider(primary, fallback)

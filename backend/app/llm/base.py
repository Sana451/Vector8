from abc import ABC, abstractmethod


class LLMProviderError(Exception):
    """The LLM provider failed or returned an unusable answer."""


class LLMProviderNotConfiguredError(LLMProviderError):
    """No API key is configured for the selected provider."""


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict[str, str]]) -> str:
        """Return the assistant reply for chat messages (role/content dicts)."""

    @abstractmethod
    def get_name(self) -> str: ...

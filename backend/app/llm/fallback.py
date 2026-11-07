import structlog

from app.llm.base import LLMProvider, LLMProviderError

logger = structlog.get_logger(__name__)


class FallbackLLMProvider(LLMProvider):
    """Calls the primary provider and retries once on any error with the fallback."""

    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    def get_name(self) -> str:
        return self._primary.get_name()

    async def complete(self, messages: list[dict[str, str]]) -> str:
        try:
            return await self._primary.complete(messages)
        except LLMProviderError as primary_exc:
            logger.warning(
                "llm_primary_failed_using_fallback",
                primary=self._primary.get_name(),
                fallback=self._fallback.get_name(),
                error=str(primary_exc),
            )

        try:
            return await self._fallback.complete(messages)
        except LLMProviderError as fallback_exc:
            raise LLMProviderError(
                f"{self._primary.get_name()} and {self._fallback.get_name()} both failed"
            ) from fallback_exc

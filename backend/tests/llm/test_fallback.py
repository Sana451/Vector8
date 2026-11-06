import pytest

from app.llm.base import LLMProvider, LLMProviderError
from app.llm.fallback import FallbackLLMProvider


class StubProvider(LLMProvider):
    def __init__(
        self, name: str, result: str | None = None, error: Exception | None = None
    ) -> None:
        self._name = name
        self._result = result
        self._error = error
        self.calls = 0

    def get_name(self) -> str:
        return self._name

    async def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


async def test_primary_success_skips_fallback() -> None:
    primary = StubProvider("groq", result="ok")
    fallback = StubProvider("sambanova", result="fb")
    provider = FallbackLLMProvider(primary, fallback)

    assert await provider.complete([]) == "ok"
    assert fallback.calls == 0


async def test_primary_error_uses_fallback() -> None:
    primary = StubProvider("groq", error=LLMProviderError("413 too large"))
    fallback = StubProvider("sambanova", result="fb")
    provider = FallbackLLMProvider(primary, fallback)

    assert await provider.complete([]) == "fb"
    assert primary.calls == 1
    assert fallback.calls == 1


async def test_both_fail_raises_llm_provider_error() -> None:
    primary = StubProvider("groq", error=LLMProviderError("429"))
    fallback = StubProvider("sambanova", error=LLMProviderError("503"))
    provider = FallbackLLMProvider(primary, fallback)

    with pytest.raises(LLMProviderError) as exc_info:
        await provider.complete([])
    assert isinstance(exc_info.value.__cause__, LLMProviderError)

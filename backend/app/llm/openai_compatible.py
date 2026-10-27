import httpx

from app.llm.base import LLMProvider, LLMProviderError


class OpenAICompatibleProvider(LLMProvider):
    """Chat-completions client for OpenAI-style APIs (Groq, OpenAI)."""

    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        temperature: float = 0.3,
    ) -> None:
        self._name = name
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._temperature = temperature

    def get_name(self) -> str:
        return self._name

    async def complete(self, messages: list[dict[str, str]]) -> str:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": self._model,
                        "messages": messages,
                        "temperature": self._temperature,
                    },
                )
                response.raise_for_status()
            content = response.json()["choices"][0]["message"].get("content")
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise LLMProviderError(f"{self._name} request failed") from exc

        if not content or not content.strip():
            raise LLMProviderError(f"{self._name} returned an empty answer")
        return str(content).strip()

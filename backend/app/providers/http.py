"""
Shared async HTTP client for external providers.

Centralizes timeout handling, API key masking in logs and mapping of HTTP
status codes onto the generic :mod:`app.providers.exceptions` hierarchy.

Adapters that need vendor-specific error payload parsing can pass their own
``error_handler`` while still reusing transport and logging behaviour.
"""

from collections.abc import Callable
from typing import Any

import httpx

from app.core.logging import get_logger
from app.providers.exceptions import (
    ProviderAuthenticationError,
    ProviderBadRequestError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

logger = get_logger(__name__)

ErrorHandler = Callable[[httpx.Response], None]


def mask_api_key(api_key: str) -> str:
    """Mask an API key for logging.

    Args:
        api_key: API key to mask.

    Returns:
        Masked API key (first 4 and last 4 characters visible).
    """
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}...{api_key[-4:]}"


class ProviderHTTPClient:
    """Thin async HTTP wrapper with provider-aware error mapping."""

    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        timeout: int,
        api_key: str | None = None,
        default_headers: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
        error_handler: ErrorHandler | None = None,
    ):
        """Initialize the client.

        Args:
            provider: Provider name used in logs and errors.
            base_url: Provider base URL.
            timeout: Request timeout in seconds.
            api_key: Optional API key (only used for masked logging here).
            default_headers: Headers merged into every request.
            client: Optional externally managed ``httpx.AsyncClient``.
            error_handler: Optional vendor-specific non-2xx handler.
        """
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key
        self.default_headers = default_headers or {}
        self._client = client
        self._error_handler = error_handler

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        tracking_id: str | None = None,
    ) -> Any:
        """Perform a request and return the decoded JSON body.

        Args:
            method: HTTP method.
            path: Path appended to ``base_url``.
            json: Optional JSON body.
            params: Optional query parameters.
            headers: Headers merged over ``default_headers``.
            tracking_id: Correlation id included in logs.

        Returns:
            Decoded JSON response body.

        Raises:
            ProviderError: Mapped from transport failures or non-2xx responses.
        """
        url = f"{self.base_url}{path}"
        merged_headers = {**self.default_headers, **(headers or {})}

        try:
            response = await self._send(
                method,
                url,
                json=json,
                params=params,
                headers=merged_headers,
            )

            logger.info(
                "Provider response received",
                provider=self.provider,
                status_code=response.status_code,
                tracking_id=tracking_id,
            )

            if response.status_code >= 400:
                self.handle_error_response(response, tracking_id=tracking_id)

            return response.json()

        except httpx.TimeoutException as exc:
            logger.error(
                "Provider request timeout",
                provider=self.provider,
                timeout_seconds=self.timeout,
                tracking_id=tracking_id,
            )
            raise ProviderTimeoutError(
                f"Request timeout after {self.timeout} seconds",
                provider=self.provider,
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "Provider HTTP error",
                provider=self.provider,
                error=str(exc),
                tracking_id=tracking_id,
            )
            raise ProviderRequestError(str(exc), provider=self.provider) from exc

    async def _send(
        self,
        method: str,
        url: str,
        *,
        json: Any | None,
        params: dict[str, Any] | None,
        headers: dict[str, str],
    ) -> httpx.Response:
        """Send the request using either the injected or a temporary client.

        Method-specific helpers (``client.post``/``client.get``) are used rather
        than ``client.request`` so that bodyless verbs never receive a ``json``
        keyword.
        """
        kwargs: dict[str, Any] = {"params": params, "headers": headers}
        if json is not None:
            kwargs["json"] = json

        if self._client is not None:
            send = getattr(self._client, method.lower())
            return await send(url, timeout=self.timeout, **kwargs)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            send = getattr(client, method.lower())
            return await send(url, **kwargs)

    def handle_error_response(
        self,
        response: httpx.Response,
        *,
        tracking_id: str | None = None,
    ) -> None:
        """Map a non-2xx response onto a provider exception.

        Delegates to the vendor-specific ``error_handler`` when supplied.

        Args:
            response: HTTP response with a >=400 status code.
            tracking_id: Correlation id included in logs.

        Raises:
            ProviderError: Always.
        """
        if self._error_handler is not None:
            self._error_handler(response)

        status_code = response.status_code
        message = self._extract_message(response)

        if status_code == 400:
            raise ProviderBadRequestError(
                message, provider=self.provider, status_code=status_code
            )
        if status_code in (401, 403):
            logger.error(
                "Provider authentication error",
                provider=self.provider,
                tracking_id=tracking_id,
                api_key=mask_api_key(self.api_key or ""),
            )
            raise ProviderAuthenticationError(
                "Authentication failed - check API key",
                provider=self.provider,
                status_code=status_code,
            )
        if status_code == 408:
            raise ProviderTimeoutError(
                message, provider=self.provider, status_code=status_code
            )
        if status_code == 429:
            raise ProviderRateLimitError(
                "Rate limit exceeded",
                provider=self.provider,
                status_code=status_code,
            )
        if status_code in (500, 502, 503, 504):
            raise ProviderUnavailableError(
                f"{self.provider} temporarily unavailable (HTTP {status_code})",
                provider=self.provider,
                status_code=status_code,
            )

        raise ProviderRequestError(
            message, provider=self.provider, status_code=status_code
        )

    @staticmethod
    def _extract_message(response: httpx.Response) -> str:
        """Best-effort extraction of a human readable error message."""
        try:
            data = response.json()
        except ValueError:
            return response.text or f"HTTP {response.status_code}"

        if isinstance(data, dict):
            detailed = data.get("detailedError")
            if isinstance(detailed, dict) and detailed.get("message"):
                return str(detailed["message"])
            for key in ("message", "error", "detail"):
                if data.get(key):
                    return str(data[key])

        return f"HTTP {response.status_code}"

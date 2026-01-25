"""HTTP client helpers for the Orcheo CLI."""

from __future__ import annotations
from collections.abc import Callable, Mapping
from typing import Any
import httpx
from orcheo_sdk.cli.errors import APICallError


class ApiClient:
    """Thin wrapper around ``httpx`` with CLI-specific defaults."""

    def __init__(
        self,
        *,
        base_url: str,
        token: str | None,
        timeout: float = 30.0,
        public_base_url: str | None = None,
        token_provider: Callable[[], str | None] | None = None,
    ) -> None:
        """Initialize the HTTP client wrapper.

        Args:
            base_url: The API base URL.
            token: Static bearer token (e.g., service token).
            timeout: Request timeout in seconds.
            public_base_url: Optional public ChatKit base URL for share links.
            token_provider: Optional callback that returns a valid token,
                used for dynamic token resolution (e.g., OAuth with refresh).
        """
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._public_base_url = public_base_url.rstrip("/") if public_base_url else None
        self._token_provider = token_provider

    @property
    def base_url(self) -> str:
        """Return the configured base URL."""
        return self._base_url

    @property
    def public_base_url(self) -> str | None:
        """Return the optional public ChatKit base URL for share links."""
        return self._public_base_url

    def _get_active_token(self) -> str | None:
        """Get the active bearer token.

        Priority: token_provider (OAuth with refresh) > static token (service token).
        """
        if self._token_provider:
            provided = self._token_provider()
            if provided:
                return provided
        return self._token

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        token = self._get_active_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def get(self, path: str, *, params: Mapping[str, Any] | None = None) -> Any:
        """Issue a GET request and return the parsed JSON payload."""
        url = f"{self._base_url}{path}"
        try:
            response = httpx.get(
                url,
                params=params,
                headers=self._headers(),
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            message = self._format_error(exc.response)
            raise APICallError(message, status_code=exc.response.status_code) from exc
        except httpx.RequestError as exc:
            raise APICallError(f"Failed to reach {url}: {exc}") from exc
        return response.json()

    def post(
        self,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
    ) -> Any:
        """Issue a POST request and return parsed JSON when available."""
        url = f"{self._base_url}{path}"
        try:
            response = httpx.post(
                url,
                json=json_body,
                headers=self._headers(),
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            message = self._format_error(exc.response)
            raise APICallError(message, status_code=exc.response.status_code) from exc
        except httpx.RequestError as exc:
            raise APICallError(f"Failed to reach {url}: {exc}") from exc

        if response.status_code == httpx.codes.NO_CONTENT:
            return None
        return response.json()

    def put(
        self,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
    ) -> Any:
        """Issue a PUT request and return parsed JSON when available."""
        url = f"{self._base_url}{path}"
        try:
            response = httpx.put(
                url,
                json=json_body,
                headers=self._headers(),
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - defensive code
            message = self._format_error(exc.response)
            raise APICallError(message, status_code=exc.response.status_code) from exc
        except httpx.RequestError as exc:  # pragma: no cover - defensive code
            raise APICallError(f"Failed to reach {url}: {exc}") from exc

        if response.status_code == httpx.codes.NO_CONTENT:
            return None
        return response.json()

    def delete(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Issue a DELETE request."""
        url = f"{self._base_url}{path}"
        try:
            # Use httpx.request for DELETE with JSON body
            # (httpx.delete doesn't support JSON bodies)
            if json_body is not None:
                response = httpx.request(
                    "DELETE",
                    url,
                    params=params,
                    json=json_body,
                    headers=self._headers(),
                    timeout=self._timeout,
                )
            else:
                response = httpx.delete(
                    url,
                    params=params,
                    headers=self._headers(),
                    timeout=self._timeout,
                )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            message = self._format_error(exc.response)
            raise APICallError(message, status_code=exc.response.status_code) from exc
        except httpx.RequestError as exc:
            raise APICallError(f"Failed to reach {url}: {exc}") from exc

        if response.status_code == httpx.codes.NO_CONTENT:
            return None
        return response.json()

    @staticmethod
    def _format_error(response: httpx.Response) -> str:
        try:
            payload = response.json()
            if isinstance(payload, Mapping):
                detail = payload.get("detail")
                if isinstance(detail, Mapping):
                    message = detail.get("message") or detail.get("detail")
                    if message:
                        return str(message)
                if "message" in payload:
                    return str(payload["message"])
            return response.text
        except Exception:  # pragma: no cover - fallback to status text
            return response.text

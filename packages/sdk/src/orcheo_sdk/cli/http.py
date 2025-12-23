"""HTTP client helpers for the Orcheo CLI."""

from __future__ import annotations
from collections.abc import Mapping
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
    ) -> None:
        """Initialize the HTTP client wrapper."""
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._public_base_url = public_base_url.rstrip("/") if public_base_url else None

    @property
    def base_url(self) -> str:
        """Return the configured base URL."""
        return self._base_url

    @property
    def public_base_url(self) -> str | None:
        """Return the optional public ChatKit base URL for share links."""
        return self._public_base_url

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
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
        except httpx.HTTPStatusError as exc:
            message = self._format_error(exc.response)
            raise APICallError(message, status_code=exc.response.status_code) from exc
        except httpx.RequestError as exc:
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

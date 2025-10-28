"""HTTP client helpers for the Orcheo CLI."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
import httpx
from .cache import CacheStore


class ApiRequestError(RuntimeError):
    """Raised when the CLI cannot complete an API request."""

    def __init__(self, message: str, *, response: httpx.Response | None = None) -> None:
        """Initialise the error with optional HTTP response context."""
        super().__init__(message)
        self.response = response


class OfflineCacheMissError(ApiRequestError):
    """Raised when offline mode is requested but no cached response exists."""


@dataclass(slots=True)
class FetchResult:
    """Wrapper describing the origin of an API payload."""

    data: Any
    from_cache: bool
    timestamp: datetime | None


class APIClient:
    """Small wrapper around :class:`httpx.Client` with caching support."""

    def __init__(
        self,
        *,
        base_url: str,
        service_token: str | None,
        cache: CacheStore,
        timeout: float = 30.0,
    ) -> None:
        """Create a client bound to the provided API endpoint."""
        headers: dict[str, str] = {"User-Agent": "orcheo-cli/1.0"}
        if service_token:
            headers["Authorization"] = f"Bearer {service_token}"
        self._client = httpx.Client(base_url=base_url, timeout=timeout, headers=headers)
        self._cache = cache

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def fetch_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        offline: bool = False,
        description: str = "resource",
    ) -> FetchResult:
        """Return JSON data from the API with cache fallbacks."""
        cache_key = self._cache.build_key(method, path, params)
        if offline:
            cached = self._cache.read(cache_key)
            if cached:
                return FetchResult(
                    data=cached.data,
                    from_cache=True,
                    timestamp=cached.timestamp,
                )
            msg = f"No cached {description} available for offline mode"
            raise OfflineCacheMissError(msg)

        try:
            response = self._client.request(method, path, params=params, json=json)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - exercised via tests
            cached = self._cache.read(cache_key)
            if cached:
                return FetchResult(
                    data=cached.data, from_cache=True, timestamp=cached.timestamp
                )
            status = exc.response.status_code
            msg = (
                f"API request failed with status {status} while fetching {description}"
            )
            raise ApiRequestError(msg, response=exc.response) from exc
        except httpx.HTTPError as exc:
            cached = self._cache.read(cache_key)
            if cached:
                return FetchResult(
                    data=cached.data, from_cache=True, timestamp=cached.timestamp
                )
            msg = f"Unable to reach Orcheo API while fetching {description}"
            raise ApiRequestError(msg) from exc

        try:
            data = response.json()
        except ValueError:
            data = None
        if method.upper() == "GET":
            self._cache.write(cache_key, data)
        return FetchResult(data=data, from_cache=False, timestamp=datetime.now(tz=UTC))

    def get_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        offline: bool = False,
        description: str = "resource",
    ) -> FetchResult:
        """Helper for GET requests returning JSON payloads."""
        return self.fetch_json(
            "GET", path, params=params, offline=offline, description=description
        )

    def post_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        description: str = "resource",
    ) -> FetchResult:
        """Helper for POST requests returning JSON payloads."""
        return self.fetch_json(
            "POST", path, params=params, json=json, description=description
        )


__all__ = [
    "APIClient",
    "ApiRequestError",
    "FetchResult",
    "OfflineCacheMissError",
]

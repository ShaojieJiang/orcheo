"""Helpers for proxying ChatKit static assets through the Orcheo server."""

from __future__ import annotations
import os
import re
from collections.abc import Mapping
import httpx
from fastapi import HTTPException, Request, Response, status
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse


_DEFAULT_CHATKIT_CDN_BASE = "https://cdn.platform.openai.com/"
_REQUEST_HEADER_ALLOWLIST = {
    "accept",
    "if-none-match",
    "if-modified-since",
    "range",
}
_RESPONSE_HEADER_ALLOWLIST = {
    "accept-ranges",
    "access-control-allow-credentials",
    "access-control-allow-origin",
    "cache-control",
    "content-length",
    "content-type",
    "etag",
    "last-modified",
    "vary",
}
_ANALYTICS_STUB_JS = """
// orcheo-analytics-stub
export const q = {
  AnalyticsBrowser: class {
    load() {
      return Promise.resolve();
    }
    ready(callback) {
      if (typeof callback === "function") {
        callback();
      }
    }
    track() {}
  },
};
""".strip()
_FETCH_GUARD_SNIPPET = """
<script data-orcheo-fetch-guard>
(() => {
  const blockedPrefixes = [
    "https://chatgpt.com/ces",
    "https://chatgpt-staging.com/ces",
    "https://chatgpt.com/backend-api",
    "https://chatgpt.com/backend-anon",
    "https://api.openai.com/v1/chatkit/domain_keys/verify",
    "https://api.openai.com/v1/chatkit/domain_keys/verify_hosted",
    "https://sentinel.openai.com",
    "https://rum.browser-intake-datadoghq.com",
    "https://browser-intake-datadoghq.com",
    "https://logs.browser-intake-datadoghq.com",
    "https://www.datadoghq-browser-agent.com",
    "https://www.datad0g-browser-agent.com",
    "https://d3uc069fcn7uxw.cloudfront.net",
    "https://d20xtzwzcl0ceb.cloudfront.net",
  ];
  const stubbedResponses = [
    {
      prefix: "https://api.openai.com/v1/chatkit/domain_keys/verify",
      body: JSON.stringify({ verified: true }),
    },
    {
      prefix: "https://api.openai.com/v1/chatkit/domain_keys/verify_hosted",
      body: JSON.stringify({ verified: true }),
    },
  ];
  const shouldBlock = (url) =>
    blockedPrefixes.some((prefix) => url.startsWith(prefix));
  const getStubResponse = (url) => {
    for (const stub of stubbedResponses) {
      if (url.startsWith(stub.prefix)) {
        return stub;
      }
    }
    return shouldBlock(url) ? { body: "{}" } : null;
  };
  const resolveUrl = (input) => {
    if (!input) {
      return "";
    }
    if (typeof input === "string") {
      try {
        return new URL(input, window.location.href).toString();
      } catch (error) {
        return input;
      }
    }
    if (typeof input === "object") {
      if ("url" in input && typeof input.url === "string") {
        return resolveUrl(input.url);
      }
      if ("href" in input && typeof input.href === "string") {
        return resolveUrl(input.href);
      }
    }
    return "";
  };
  const originalFetch = window.fetch ? window.fetch.bind(window) : null;
  if (originalFetch) {
    window.fetch = (input, init) => {
      try {
        const url = resolveUrl(input);
        const stub = url ? getStubResponse(url) : null;
        if (stub) {
          return Promise.resolve(
            new Response(stub.body || "{}", {
              status: 200,
              headers: { "Content-Type": "application/json" },
            })
          );
        }
      } catch (error) {}
      return originalFetch(input, init);
    };
  }
  if (navigator && typeof navigator.sendBeacon === "function") {
    const originalBeacon = navigator.sendBeacon.bind(navigator);
    navigator.sendBeacon = (url, data) => {
      const resolved = resolveUrl(url);
      return resolved && getStubResponse(resolved)
        ? true
        : originalBeacon(url, data);
    };
  }
  if (window.XMLHttpRequest && window.XMLHttpRequest.prototype) {
    const originalOpen = window.XMLHttpRequest.prototype.open;
    const originalSend = window.XMLHttpRequest.prototype.send;
    window.XMLHttpRequest.prototype.open = function (method, url) {
      const resolved = resolveUrl(url);
      const stub = resolved ? getStubResponse(resolved) : null;
      this.__orcheoStubResponse = stub;
      return stub
        ? undefined
        : originalOpen.apply(this, arguments);
    };
    window.XMLHttpRequest.prototype.send = function () {
      const stub = this.__orcheoStubResponse;
      if (stub) {
        const body = stub.body || "{}";
        try {
          Object.defineProperty(this, "readyState", {
            value: 4,
            configurable: true,
          });
          Object.defineProperty(this, "status", {
            value: 200,
            configurable: true,
          });
          Object.defineProperty(this, "responseText", {
            value: body,
            configurable: true,
          });
          Object.defineProperty(this, "response", {
            value: body,
            configurable: true,
          });
        } catch (error) {}
        setTimeout(() => {
          if (typeof this.onreadystatechange === "function") {
            this.onreadystatechange();
          }
          if (typeof this.onload === "function") {
            this.onload();
          }
          if (typeof this.onloadend === "function") {
            this.onloadend();
          }
        }, 0);
        return undefined;
      }
      return originalSend.apply(this, arguments);
    };
  }
})();
</script>
""".strip()


def _normalize_base(value: str) -> str:
    return value if value.endswith("/") else f"{value}/"


def _normalize_path_prefix(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        return "/"
    if not trimmed.startswith("/"):
        trimmed = f"/{trimmed}"
    return trimmed if trimmed.endswith("/") else f"{trimmed}/"


def _resolve_cdn_base() -> str:
    raw = os.getenv("ORCHEO_CHATKIT_CDN_BASE_URL", "").strip()
    base = raw or _DEFAULT_CHATKIT_CDN_BASE
    return _normalize_base(base)


def _sanitize_asset_path(asset_path: str) -> str:
    cleaned = asset_path.strip("/")
    if not cleaned or ".." in cleaned.split("/"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ChatKit asset not found.",
        )
    return cleaned


def _filter_headers(headers: Mapping[str, str], allowlist: set[str]) -> dict[str, str]:
    return {key: value for key, value in headers.items() if key.lower() in allowlist}


def _strip_cloudflare_challenge(html: str) -> str:
    """Remove Cloudflare challenge scripts that would fail when proxied."""
    # The challenge script is an inline <script> that loads /cdn-cgi/... via
    # dynamically created script tags. Since this path doesn't exist on the
    # Orcheo server, the script would fail and potentially block rendering.
    return re.sub(
        r"<script>[^<]*?/cdn-cgi/challenge-platform/[^<]*?</script>",
        "",
        html,
        flags=re.DOTALL,
    )


def _rewrite_chatkit_html(html: str, asset_prefix: str) -> str:
    normalized_prefix = _normalize_path_prefix(asset_prefix)
    rewritten = (
        html.replace('href="/assets/ck1/', f'href="{normalized_prefix}')
        .replace("href='/assets/ck1/", f"href='{normalized_prefix}")
        .replace('src="/assets/ck1/', f'src="{normalized_prefix}')
        .replace("src='/assets/ck1/", f"src='{normalized_prefix}")
    )
    stripped = _strip_cloudflare_challenge(rewritten)
    return _inject_fetch_guard(stripped)


def _is_analytics_bundle(payload: bytes) -> bool:
    # Only stub small bundles (< 500KB) that are dedicated analytics code.
    # The main application bundle is several MB and may reference analytics
    # strings without being a dedicated analytics bundle.
    if len(payload) > 500_000:
        return False
    return b"AnalyticsBrowser" in payload and b"Segment.io" in payload


def _inject_fetch_guard(html: str) -> str:
    if "data-orcheo-fetch-guard" in html:
        return html
    match = re.search(r"<head\b[^>]*>", html, re.IGNORECASE)
    if not match:
        return html
    insert_at = match.end()
    return f"{html[:insert_at]}{_FETCH_GUARD_SNIPPET}{html[insert_at:]}"


async def _close_proxy(
    upstream: httpx.Response,
    client: httpx.AsyncClient,
) -> None:
    await upstream.aclose()
    await client.aclose()


async def proxy_chatkit_asset(
    request: Request,
    *,
    prefix: str,
    asset_path: str,
    rewrite_prefix: str | None = None,
) -> Response:
    """Proxy a ChatKit static asset from the configured CDN base."""
    clean_path = _sanitize_asset_path(asset_path)
    base = _resolve_cdn_base()
    prefix = prefix if prefix.endswith("/") else f"{prefix}/"
    upstream_url = f"{base}{prefix}{clean_path}"
    if request.url.query:
        upstream_url = f"{upstream_url}?{request.url.query}"

    method = request.method.upper()
    if method not in {"GET", "HEAD"}:
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED)

    headers = _filter_headers(request.headers, _REQUEST_HEADER_ALLOWLIST)
    headers["accept-encoding"] = "identity"

    client = httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(10.0, connect=5.0),
    )
    try:
        upstream_request = client.build_request(method, upstream_url, headers=headers)
        upstream = await client.send(upstream_request, stream=True)
    except httpx.RequestError as exc:
        await client.aclose()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch ChatKit asset.",
        ) from exc

    content_type = upstream.headers.get("content-type", "").lower()
    if (
        rewrite_prefix
        and method == "GET"
        and "text/html" in content_type
        and upstream.status_code < 400
    ):
        try:
            body = await upstream.aread()
        finally:
            await _close_proxy(upstream, client)
        encoding = upstream.encoding or "utf-8"
        html = body.decode(encoding, errors="replace")
        rewritten = _rewrite_chatkit_html(html, rewrite_prefix)
        response_headers = _filter_headers(upstream.headers, _RESPONSE_HEADER_ALLOWLIST)
        response_headers.pop("content-length", None)
        return Response(
            content=rewritten,
            status_code=upstream.status_code,
            headers=response_headers,
        )

    if (
        method == "GET"
        and upstream.status_code < 400
        and "javascript" in content_type
        and clean_path.startswith("index-")
        and clean_path.endswith(".js")
    ):
        try:
            body = await upstream.aread()
        finally:
            await _close_proxy(upstream, client)
        if _is_analytics_bundle(body):
            response_headers = _filter_headers(
                upstream.headers, _RESPONSE_HEADER_ALLOWLIST
            )
            response_headers.pop("content-length", None)
            return Response(
                content=_ANALYTICS_STUB_JS,
                status_code=upstream.status_code,
                headers=response_headers,
                media_type="application/javascript",
            )
        response_headers = _filter_headers(upstream.headers, _RESPONSE_HEADER_ALLOWLIST)
        response_headers.pop("content-length", None)
        return Response(
            content=body,
            status_code=upstream.status_code,
            headers=response_headers,
        )

    response_headers = _filter_headers(upstream.headers, _RESPONSE_HEADER_ALLOWLIST)
    background = BackgroundTask(_close_proxy, upstream, client)
    return StreamingResponse(
        upstream.aiter_bytes(),
        status_code=upstream.status_code,
        headers=response_headers,
        background=background,
    )


__all__ = ["proxy_chatkit_asset"]

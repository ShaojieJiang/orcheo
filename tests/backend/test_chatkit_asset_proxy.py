"""Tests for ChatKit asset proxy helpers."""

from __future__ import annotations

from orcheo_backend.app.chatkit_asset_proxy import _RESPONSE_HEADER_ALLOWLIST


def testresponse_header_allowlist_includes_content_range() -> None:
    """Content-Range is preserved for partial responses."""
    assert "content-range" in _RESPONSE_HEADER_ALLOWLIST

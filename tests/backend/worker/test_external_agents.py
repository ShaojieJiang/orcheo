"""Tests for worker-side external agent login helpers."""

from __future__ import annotations
from orcheo_backend.worker.external_agents import _extract_auth_url


def test_extract_auth_url_prefers_public_url_over_localhost() -> None:
    """Public auth links should win over worker-local callback URLs."""
    output = """
Starting local login server on http://localhost:1455.
If your browser did not open, navigate to this URL to authenticate:
https://auth.openai.com/oauth/authorize?response_type=code
"""

    assert (
        _extract_auth_url(output)
        == "https://auth.openai.com/oauth/authorize?response_type=code"
    )

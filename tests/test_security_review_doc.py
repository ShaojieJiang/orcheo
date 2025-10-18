"""Ensure the security review report remains present and structured."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "section",
    [
        "## Methodology",
        "## Vault Findings",
        "## Trigger & Execution Findings",
        "## Mitigations & Follow-up",
    ],
)
def test_security_review_sections(section: str) -> None:
    report = (REPO_ROOT / "docs" / "security_review.md").read_text(encoding="utf-8")
    assert section in report

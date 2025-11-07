"""Placeholder parsing and :class:`CredentialReference` helpers."""

from __future__ import annotations
import re
from collections.abc import Iterable
from dataclasses import dataclass


_PLACEHOLDER_PATTERN = re.compile(r"^\[\[(?P<body>.+)\]\]$")


@dataclass(frozen=True, slots=True)
class CredentialReference:
    """Opaque descriptor pointing to a credential payload."""

    identifier: str
    payload_path: tuple[str, ...] = ("secret",)

    @classmethod
    def from_placeholder(cls, value: str) -> CredentialReference | None:
        """Return a reference extracted from a ``[[credential]]`` placeholder."""
        match = _PLACEHOLDER_PATTERN.fullmatch(value.strip())
        if not match:
            return None
        body = match.group("body").strip()
        if not body:
            return None
        identifier, payload = _split_placeholder_body(body)
        if not identifier:
            return None
        if not payload:
            payload = ("secret",)
        return cls(identifier=identifier, payload_path=payload)


def credential_ref(
    identifier: str,
    payload: str | Iterable[str] = "secret",
) -> CredentialReference:
    """Return a :class:`CredentialReference` for Python-authored graphs."""
    normalized_identifier = identifier.strip()
    if not normalized_identifier:
        msg = "Credential identifier must be a non-empty string"
        raise ValueError(msg)
    if isinstance(payload, str):
        payload_parts = tuple(
            part.strip() for part in payload.split(".") if part.strip()
        )
    else:
        payload_parts = tuple(
            str(part).strip() for part in payload if str(part).strip()
        )
    if not payload_parts:
        payload_parts = ("secret",)
    return CredentialReference(
        identifier=normalized_identifier,
        payload_path=payload_parts,
    )


def parse_credential_reference(value: str) -> CredentialReference | None:
    """Return a credential reference encoded within the provided string."""
    return CredentialReference.from_placeholder(value)


def _split_placeholder_body(body: str) -> tuple[str, tuple[str, ...]]:
    """Split a placeholder body into identifier and payload path."""
    if "#" not in body:
        return body, ()
    identifier, raw_path = body.split("#", 1)
    path_parts = tuple(part.strip() for part in raw_path.split(".") if part.strip())
    return identifier.strip(), path_parts


__all__ = [
    "CredentialReference",
    "credential_ref",
    "parse_credential_reference",
]

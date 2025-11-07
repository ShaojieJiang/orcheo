"""Shared request context objects for ChatKit integrations."""

from __future__ import annotations
from typing import TypedDict
from pydantic import BaseModel


class ChatKitRequestContext(TypedDict, total=False):
    """Context passed to store operations and response handlers."""

    chatkit_request: BaseModel


__all__ = ["ChatKitRequestContext"]

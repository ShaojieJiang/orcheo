"""Backward-compatible imports for the ChatKit service layer.

The original monolithic ``chatkit_service`` module exceeded our linting limits.
To make the codebase easier to navigate, the implementation now lives inside
``orcheo_backend.app.chatkit``. Keeping this module allows existing imports to
continue working while we roll out the new package structure.
"""

from orcheo.config import get_settings
from orcheo.graph.builder import build_graph
from orcheo_backend.app.chatkit import (
    ChatKitRequestContext,
    InMemoryChatKitStore,
    OrcheoChatKitServer,
    create_chatkit_server,
)
from orcheo_backend.app.chatkit.message_utils import (
    build_initial_state as _build_initial_state,
)
from orcheo_backend.app.chatkit.message_utils import (
    collect_text_from_assistant_content as _collect_text_from_assistant_content,
)
from orcheo_backend.app.chatkit.message_utils import (
    collect_text_from_user_content as _collect_text_from_user_content,
)
from orcheo_backend.app.chatkit.message_utils import (
    extract_reply_from_state as _extract_reply_from_state,
)
from orcheo_backend.app.chatkit.message_utils import (
    stringify_langchain_message as _stringify_langchain_message,
)


__all__ = [
    "ChatKitRequestContext",
    "InMemoryChatKitStore",
    "OrcheoChatKitServer",
    "create_chatkit_server",
    "_build_initial_state",
    "_collect_text_from_assistant_content",
    "_collect_text_from_user_content",
    "_extract_reply_from_state",
    "_stringify_langchain_message",
    "build_graph",
    "get_settings",
]

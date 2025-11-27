"""Tests for ChatKit message helpers."""

from __future__ import annotations
from datetime import UTC, datetime
from pathlib import Path
from chatkit.types import (
    FileAttachment,
    InferenceOptions,
    ThreadMetadata,
    UserMessageItem,
    UserMessageTextContent,
)
from orcheo_backend.app.chatkit import messages as chatkit_messages
from orcheo_backend.app.chatkit.messages import build_inputs_payload


def test_build_inputs_payload_converts_file_attachments(
    monkeypatch, tmp_path: Path
) -> None:
    """File attachments are converted into documents with storage paths."""

    class FakeSettings:
        def __init__(self, storage_base: Path) -> None:
            self._storage_base = storage_base

        def get(self, key: str, default: object | None = None) -> object | None:
            if key == "CHATKIT_STORAGE_PATH":
                return str(self._storage_base)
            return default

    storage_base = tmp_path / "chatkit"
    monkeypatch.setattr(
        chatkit_messages, "get_settings", lambda: FakeSettings(storage_base)
    )

    thread = ThreadMetadata(
        id="thr_docs",
        created_at=datetime.now(UTC),
        metadata={},
    )
    user_item = UserMessageItem(
        id="msg_docs",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="Hello")],
        attachments=[
            FileAttachment(
                id="atc123",
                name="notes.txt",
                mime_type="text/plain",
            )
        ],
        inference_options=InferenceOptions(model="gpt-5"),
    )

    payload = build_inputs_payload(thread, "Hi", [], user_item)

    assert "documents" in payload
    documents = payload["documents"]
    assert isinstance(documents, list)
    assert documents[0]["storage_path"] == str(storage_base / "atc123_notes.txt")
    assert documents[0]["source"] == "notes.txt"
    metadata = documents[0]["metadata"]
    assert metadata["mime_type"] == "text/plain"
    assert metadata["attachment_id"] == "atc123"

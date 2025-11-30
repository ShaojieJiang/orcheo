"""Tests for ChatKit message helpers."""

from __future__ import annotations
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import pytest
from chatkit.errors import CustomStreamError
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageItem,
    FileAttachment,
    InferenceOptions,
    Page,
    ThreadMetadata,
    UserMessageItem,
    UserMessageTextContent,
)
from fastapi import UploadFile
from starlette.datastructures import Headers
from orcheo_backend.app.chatkit import messages as chatkit_messages
from orcheo_backend.app.chatkit.context import ChatKitRequestContext
from orcheo_backend.app.chatkit.messages import (
    build_assistant_item,
    build_history,
    build_inputs_payload,
    record_run_metadata,
    require_workflow_id,
    resolve_user_item,
)
from orcheo_backend.app.repository import WorkflowRun


@pytest.mark.asyncio
async def test_build_history_converts_thread_items() -> None:
    """Test build_history converts user and assistant messages to ChatML format."""
    thread = ThreadMetadata(
        id="thr_history",
        created_at=datetime.now(UTC),
        metadata={},
    )

    user_msg = UserMessageItem(
        id="msg_user",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="Hello AI")],
        inference_options=InferenceOptions(model="gpt-4"),
    )

    assistant_msg = AssistantMessageItem(
        id="msg_asst",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[AssistantMessageContent(text="Hello human!")],
    )

    mock_store = MagicMock()
    mock_store.load_thread_items = AsyncMock(
        return_value=Page(
            data=[user_msg, assistant_msg],
            has_more=False,
        )
    )

    context = ChatKitRequestContext(user_id="user123")  # type: ignore[typeddict-unknown-key]
    history = await build_history(mock_store, thread, context)

    assert len(history) == 2
    assert history[0] == {"role": "user", "content": "Hello AI"}
    assert history[1] == {"role": "assistant", "content": "Hello human!"}

    mock_store.load_thread_items.assert_called_once_with(
        thread.id,
        after=None,
        limit=200,
        order="asc",
        context=context,
    )


def test_require_workflow_id_extracts_valid_uuid() -> None:
    """Test require_workflow_id returns UUID when valid."""
    workflow_id = uuid4()
    thread = ThreadMetadata(
        id="thr_valid",
        created_at=datetime.now(UTC),
        metadata={"workflow_id": str(workflow_id)},
    )

    result = require_workflow_id(thread)
    assert result == workflow_id


def test_require_workflow_id_raises_when_missing() -> None:
    """Test require_workflow_id raises CustomStreamError when workflow_id is missing."""
    thread = ThreadMetadata(
        id="thr_no_workflow",
        created_at=datetime.now(UTC),
        metadata={},
    )

    with pytest.raises(CustomStreamError) as exc_info:
        require_workflow_id(thread)

    assert "No workflow has been associated" in str(exc_info.value)
    assert exc_info.value.allow_retry is False


def test_require_workflow_id_raises_when_invalid() -> None:
    """Test require_workflow_id raises CustomStreamError for invalid UUID."""
    thread = ThreadMetadata(
        id="thr_bad_uuid",
        created_at=datetime.now(UTC),
        metadata={"workflow_id": "not-a-uuid"},
    )

    with pytest.raises(CustomStreamError) as exc_info:
        require_workflow_id(thread)

    assert "invalid" in str(exc_info.value).lower()
    assert exc_info.value.allow_retry is False


@pytest.mark.asyncio
async def test_resolve_user_item_returns_provided_item() -> None:
    """Test resolve_user_item returns the item when provided."""
    thread = ThreadMetadata(
        id="thr_resolve",
        created_at=datetime.now(UTC),
        metadata={},
    )

    user_item = UserMessageItem(
        id="msg_provided",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="Test")],
        inference_options=InferenceOptions(model="gpt-4"),
    )

    mock_store = MagicMock()
    context = ChatKitRequestContext(user_id="user123")  # type: ignore[typeddict-unknown-key]

    result = await resolve_user_item(mock_store, thread, user_item, context)

    assert result == user_item
    mock_store.load_thread_items.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_user_item_fetches_when_none() -> None:
    """Test resolve_user_item fetches latest user message when item is None."""
    thread = ThreadMetadata(
        id="thr_fetch",
        created_at=datetime.now(UTC),
        metadata={},
    )

    user_msg = UserMessageItem(
        id="msg_fetched",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="Latest message")],
        inference_options=InferenceOptions(model="gpt-4"),
    )

    mock_store = MagicMock()
    mock_store.load_thread_items = AsyncMock(
        return_value=Page(data=[user_msg], has_more=False)
    )

    context = ChatKitRequestContext(user_id="user123")  # type: ignore[typeddict-unknown-key]
    result = await resolve_user_item(mock_store, thread, None, context)

    assert result == user_msg
    mock_store.load_thread_items.assert_called_once_with(
        thread.id, after=None, limit=1, order="desc", context=context
    )


@pytest.mark.asyncio
async def test_resolve_user_item_raises_when_no_user_message() -> None:
    """Test resolve_user_item raises error when no user message found."""
    thread = ThreadMetadata(
        id="thr_no_user",
        created_at=datetime.now(UTC),
        metadata={},
    )

    # Return only assistant message
    assistant_msg = AssistantMessageItem(
        id="msg_asst",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[AssistantMessageContent(text="Only assistant")],
    )

    mock_store = MagicMock()
    mock_store.load_thread_items = AsyncMock(
        return_value=Page(data=[assistant_msg], has_more=False)
    )

    context = ChatKitRequestContext(user_id="user123")  # type: ignore[typeddict-unknown-key]

    with pytest.raises(CustomStreamError) as exc_info:
        await resolve_user_item(mock_store, thread, None, context)

    assert "Unable to locate the user message" in str(exc_info.value)
    assert exc_info.value.allow_retry is False


def test_build_inputs_payload_basic() -> None:
    """Test build_inputs_payload creates basic payload without attachments."""
    thread = ThreadMetadata(
        id="thr_basic",
        created_at=datetime.now(UTC),
        metadata={"key": "value"},
    )

    payload = build_inputs_payload(thread, "Hello", [{"role": "user", "content": "Hi"}])

    assert payload["message"] == "Hello"
    assert payload["history"] == [{"role": "user", "content": "Hi"}]
    assert payload["thread_id"] == "thr_basic"
    assert payload["metadata"] == {"key": "value"}
    assert "documents" not in payload


def test_build_inputs_payload_with_no_attachments_attribute() -> None:
    """Test build_inputs_payload when user_item has no attachments attribute."""
    thread = ThreadMetadata(
        id="thr_no_attr",
        created_at=datetime.now(UTC),
        metadata={},
    )

    # Create a mock object without attachments attribute
    user_item = MagicMock(spec=[])

    payload = build_inputs_payload(thread, "Test", [], user_item)

    assert "documents" not in payload


def test_build_inputs_payload_with_none_attachments() -> None:
    """Test build_inputs_payload when attachments is None."""
    thread = ThreadMetadata(
        id="thr_none_attach",
        created_at=datetime.now(UTC),
        metadata={},
    )

    user_item = MagicMock()
    user_item.attachments = None

    payload = build_inputs_payload(thread, "Test", [], user_item)

    assert "documents" not in payload


def test_build_inputs_payload_with_empty_attachments() -> None:
    """Test build_inputs_payload when attachments is empty list."""
    thread = ThreadMetadata(
        id="thr_empty_attach",
        created_at=datetime.now(UTC),
        metadata={},
    )

    user_item = UserMessageItem(
        id="msg_empty",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="Test")],
        attachments=[],
        inference_options=InferenceOptions(model="gpt-4"),
    )

    payload = build_inputs_payload(thread, "Test", [], user_item)

    assert "documents" not in payload


def test_build_inputs_payload_with_dict_attachments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test build_inputs_payload handles dict-format attachments."""

    class FakeSettings:
        def get(self, key: str, default: object | None = None) -> object | None:
            return default

    monkeypatch.setattr(chatkit_messages, "get_settings", lambda: FakeSettings())

    thread = ThreadMetadata(
        id="thr_dict",
        created_at=datetime.now(UTC),
        metadata={},
    )

    user_item = MagicMock()
    user_item.attachments = [
        {
            "content": "File content here",
            "filename": "test.txt",
            "content_type": "text/plain",
            "size": 100,
            "file_id": "file_123",
        }
    ]

    payload = build_inputs_payload(thread, "Test", [], user_item)

    assert "documents" in payload
    documents = payload["documents"]
    assert len(documents) == 1
    assert documents[0]["content"] == "File content here"
    assert documents[0]["source"] == "test.txt"
    assert documents[0]["metadata"]["type"] == "text/plain"
    assert documents[0]["metadata"]["size"] == 100
    assert documents[0]["metadata"]["file_id"] == "file_123"


def test_build_inputs_payload_with_dict_attachments_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test build_inputs_payload handles dict attachments with missing fields."""

    class FakeSettings:
        def get(self, key: str, default: object | None = None) -> object | None:
            return default

    monkeypatch.setattr(chatkit_messages, "get_settings", lambda: FakeSettings())

    thread = ThreadMetadata(
        id="thr_dict_defaults",
        created_at=datetime.now(UTC),
        metadata={},
    )

    user_item = MagicMock()
    user_item.attachments = [{}]  # Empty dict

    payload = build_inputs_payload(thread, "Test", [], user_item)

    assert "documents" in payload
    documents = payload["documents"]
    assert len(documents) == 1
    assert documents[0]["content"] == ""
    assert documents[0]["source"] == "unknown"
    assert documents[0]["metadata"]["type"] == "text/plain"
    assert documents[0]["metadata"]["size"] == 0
    assert documents[0]["metadata"]["file_id"] == ""


def test_build_inputs_payload_converts_file_attachments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
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


def test_build_inputs_payload_with_mixed_attachments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test build_inputs_payload handles mixed dict and FileAttachment types."""

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
        id="thr_mixed",
        created_at=datetime.now(UTC),
        metadata={},
    )

    user_item = UserMessageItem(
        id="msg_mixed",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="Hello")],
        attachments=[
            FileAttachment(
                id="atc123",
                name="notes.txt",
                mime_type="text/plain",
            ),
            FileAttachment(
                id="atc456",
                name="data.json",
                mime_type="application/json",
            ),
        ],
        inference_options=InferenceOptions(model="gpt-4"),
    )

    payload = build_inputs_payload(thread, "Hi", [], user_item)

    assert "documents" in payload
    documents = payload["documents"]
    assert len(documents) == 2
    assert documents[0]["storage_path"] == str(storage_base / "atc123_notes.txt")
    assert documents[1]["storage_path"] == str(storage_base / "atc456_data.json")


def test_record_run_metadata_with_run() -> None:
    """Test record_run_metadata updates thread metadata with run info."""
    thread = ThreadMetadata(
        id="thr_run",
        created_at=datetime.now(UTC),
        metadata={},
    )

    run = WorkflowRun(
        id=uuid4(),
        workflow_version_id=uuid4(),
        triggered_by="user",
        created_at=datetime.now(UTC),
    )

    record_run_metadata(thread, run)

    assert "last_run_at" in thread.metadata
    assert "last_run_id" in thread.metadata
    assert thread.metadata["last_run_id"] == str(run.id)
    assert "runs" in thread.metadata
    assert str(run.id) in thread.metadata["runs"]


def test_record_run_metadata_without_run() -> None:
    """Test record_run_metadata updates thread metadata without run."""
    thread = ThreadMetadata(
        id="thr_no_run",
        created_at=datetime.now(UTC),
        metadata={},
    )

    record_run_metadata(thread, None)

    assert "last_run_at" in thread.metadata
    assert "last_run_id" not in thread.metadata
    assert "runs" not in thread.metadata


def test_record_run_metadata_preserves_existing_runs() -> None:
    """Test record_run_metadata preserves existing runs list."""
    existing_run_id = str(uuid4())
    thread = ThreadMetadata(
        id="thr_preserve",
        created_at=datetime.now(UTC),
        metadata={"runs": [existing_run_id]},
    )

    run = WorkflowRun(
        id=uuid4(),
        workflow_version_id=uuid4(),
        triggered_by="user",
        created_at=datetime.now(UTC),
    )

    record_run_metadata(thread, run)

    assert len(thread.metadata["runs"]) == 2
    assert existing_run_id in thread.metadata["runs"]
    assert str(run.id) in thread.metadata["runs"]


def test_record_run_metadata_limits_runs_list() -> None:
    """Test record_run_metadata limits runs list to 20 most recent."""
    # Create 21 existing runs
    existing_runs = [str(uuid4()) for _ in range(21)]
    thread = ThreadMetadata(
        id="thr_limit",
        created_at=datetime.now(UTC),
        metadata={"runs": existing_runs},
    )

    run = WorkflowRun(
        id=uuid4(),
        workflow_version_id=uuid4(),
        triggered_by="user",
        created_at=datetime.now(UTC),
    )

    record_run_metadata(thread, run)

    # Should only keep last 20 runs
    assert len(thread.metadata["runs"]) == 20
    # Most recent run should be in the list
    assert str(run.id) in thread.metadata["runs"]
    # First run should be dropped
    assert existing_runs[0] not in thread.metadata["runs"]


def test_record_run_metadata_handles_non_list_runs() -> None:
    """Test record_run_metadata handles when runs is not a list."""
    thread = ThreadMetadata(
        id="thr_bad_runs",
        created_at=datetime.now(UTC),
        metadata={"runs": "not-a-list"},
    )

    run = WorkflowRun(
        id=uuid4(),
        workflow_version_id=uuid4(),
        triggered_by="user",
        created_at=datetime.now(UTC),
    )

    record_run_metadata(thread, run)

    # Should create a new list
    assert isinstance(thread.metadata["runs"], list)
    assert str(run.id) in thread.metadata["runs"]


def test_build_assistant_item() -> None:
    """Test build_assistant_item creates proper AssistantMessageItem."""
    thread = ThreadMetadata(
        id="thr_asst",
        created_at=datetime.now(UTC),
        metadata={},
    )

    mock_store = MagicMock()
    mock_store.generate_item_id.return_value = "msg_generated"

    context = ChatKitRequestContext(user_id="user123")  # type: ignore[typeddict-unknown-key]

    item = build_assistant_item(mock_store, thread, "Assistant reply", context)

    assert isinstance(item, AssistantMessageItem)
    assert item.id == "msg_generated"
    assert item.thread_id == thread.id
    assert len(item.content) == 1
    assert item.content[0].text == "Assistant reply"

    mock_store.generate_item_id.assert_called_once_with("message", thread, context)


@pytest.mark.asyncio
async def test_upload_chatkit_file_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test successful file upload with UTF-8 encoding."""
    from orcheo_backend.app.routers.chatkit import upload_chatkit_file

    # Setup storage path
    storage_base = tmp_path / "chatkit_storage"

    class FakeSettings:
        def get(self, key: str, default: object | None = None) -> object | None:
            if key == "CHATKIT_STORAGE_PATH":
                return str(storage_base)
            return default

    monkeypatch.setattr("orcheo.config.get_settings", lambda: FakeSettings())

    # Mock ChatKit server and store
    mock_store = MagicMock()
    mock_store.save_attachment = AsyncMock()
    mock_server = MagicMock()
    mock_server.store = mock_store

    with patch(
        "orcheo_backend.app.routers.chatkit._resolve_chatkit_server",
        return_value=mock_server,
    ):
        # Create test file
        file_content = b"Hello, this is a UTF-8 text file!"
        headers = Headers({"content-type": "text/plain"})
        upload_file = UploadFile(
            file=BytesIO(file_content), filename="test.txt", headers=headers
        )
        mock_request = MagicMock()

        # Call the upload endpoint
        response = await upload_chatkit_file(upload_file, mock_request)

        # Verify response
        assert response.status_code == 200
        body = response.body.decode("utf-8")  # type: ignore[union-attr]
        import json

        data = json.loads(body)
        assert "id" in data
        assert data["id"].startswith("atc_")
        assert data["name"] == "test.txt"
        assert data["mime_type"] == "text/plain"
        assert data["type"] == "file"
        assert data["size"] == len(file_content)
        assert "storage_path" in data

        # Verify file was saved
        storage_path = Path(data["storage_path"])
        assert storage_path.exists()
        assert storage_path.read_bytes() == file_content

        # Verify store was called
        mock_store.save_attachment.assert_called_once()


@pytest.mark.asyncio
async def test_upload_chatkit_file_utf8_encoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test file upload with UTF-8 encoding."""
    from orcheo_backend.app.routers.chatkit import upload_chatkit_file

    storage_base = tmp_path / "chatkit_storage"

    class FakeSettings:
        def get(self, key: str, default: object | None = None) -> object | None:
            if key == "CHATKIT_STORAGE_PATH":
                return str(storage_base)
            return default

    monkeypatch.setattr("orcheo.config.get_settings", lambda: FakeSettings())

    mock_store = MagicMock()
    mock_store.save_attachment = AsyncMock()
    mock_server = MagicMock()
    mock_server.store = mock_store

    with patch(
        "orcheo_backend.app.routers.chatkit._resolve_chatkit_server",
        return_value=mock_server,
    ):
        # UTF-8 encoded content with special characters
        file_content = "Hello 世界 🌍".encode()
        headers = Headers({"content-type": "text/plain"})
        upload_file = UploadFile(
            file=BytesIO(file_content), filename="utf8.txt", headers=headers
        )
        mock_request = MagicMock()

        response = await upload_chatkit_file(upload_file, mock_request)

        assert response.status_code == 200


@pytest.mark.asyncio
async def test_upload_chatkit_file_latin1_encoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test file upload with latin-1 encoding (non-UTF-8 but valid)."""
    from orcheo_backend.app.routers.chatkit import upload_chatkit_file

    storage_base = tmp_path / "chatkit_storage"

    class FakeSettings:
        def get(self, key: str, default: object | None = None) -> object | None:
            if key == "CHATKIT_STORAGE_PATH":
                return str(storage_base)
            return default

    monkeypatch.setattr("orcheo.config.get_settings", lambda: FakeSettings())

    mock_store = MagicMock()
    mock_store.save_attachment = AsyncMock()
    mock_server = MagicMock()
    mock_server.store = mock_store

    with patch(
        "orcheo_backend.app.routers.chatkit._resolve_chatkit_server",
        return_value=mock_server,
    ):
        # Latin-1 encoded content (valid in latin-1 but not UTF-8)
        file_content = "café résumé".encode("latin-1")
        headers = Headers({"content-type": "text/plain"})
        upload_file = UploadFile(
            file=BytesIO(file_content), filename="latin1.txt", headers=headers
        )
        mock_request = MagicMock()

        response = await upload_chatkit_file(upload_file, mock_request)

        assert response.status_code == 200


@pytest.mark.asyncio
async def test_upload_chatkit_file_no_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test file upload without filename uses default."""
    from orcheo_backend.app.routers.chatkit import upload_chatkit_file

    storage_base = tmp_path / "chatkit_storage"

    class FakeSettings:
        def get(self, key: str, default: object | None = None) -> object | None:
            if key == "CHATKIT_STORAGE_PATH":
                return str(storage_base)
            return default

    monkeypatch.setattr("orcheo.config.get_settings", lambda: FakeSettings())

    mock_store = MagicMock()
    mock_store.save_attachment = AsyncMock()
    mock_server = MagicMock()
    mock_server.store = mock_store

    with patch(
        "orcheo_backend.app.routers.chatkit._resolve_chatkit_server",
        return_value=mock_server,
    ):
        file_content = b"Test content"
        upload_file = UploadFile(file=BytesIO(file_content), filename=None)
        mock_request = MagicMock()

        response = await upload_chatkit_file(upload_file, mock_request)

        assert response.status_code == 200
        import json

        data = json.loads(response.body.decode("utf-8"))  # type: ignore[union-attr]
        assert data["name"] == "uploaded_file"
        assert data["mime_type"] == "text/plain"
        assert "uploaded_file" in data["storage_path"]


def test_sanitize_filename_returns_default_when_normalized_empty() -> None:
    """Ensure filenames without safe characters fall back to default name."""
    from orcheo_backend.app.routers.chatkit import _sanitize_filename

    assert _sanitize_filename("...") == "uploaded_file"


@pytest.mark.asyncio
async def test_upload_chatkit_file_invalid_filename_path_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test upload guard rejects filenames that resolve outside storage base."""
    from fastapi import HTTPException
    from orcheo_backend.app.routers import chatkit as chatkit_router
    from orcheo_backend.app.routers.chatkit import upload_chatkit_file

    storage_base = tmp_path / "chatkit_storage"

    class FakeSettings:
        def get(self, key: str, default: object | None = None) -> object | None:
            if key == "CHATKIT_STORAGE_PATH":
                return str(storage_base)
            return default

    monkeypatch.setattr("orcheo.config.get_settings", lambda: FakeSettings())

    mock_store = MagicMock()
    mock_store.save_attachment = AsyncMock()
    mock_server = MagicMock()
    mock_server.store = mock_store

    # Force sanitize helper to return a traversal attempt
    monkeypatch.setattr(
        chatkit_router,
        "_sanitize_filename",
        lambda filename: "../../../../../escape.txt",
    )

    with patch(
        "orcheo_backend.app.routers.chatkit._resolve_chatkit_server",
        return_value=mock_server,
    ):
        headers = Headers({"content-type": "text/plain"})
        upload_file = UploadFile(
            file=BytesIO(b"malicious payload"), filename="evil.txt", headers=headers
        )
        mock_request = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await upload_chatkit_file(upload_file, mock_request)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "chatkit.upload.invalid_filename"


@pytest.mark.asyncio
async def test_upload_chatkit_file_exception_handling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test file upload exception handling for general errors."""
    from fastapi import HTTPException
    from orcheo_backend.app.routers.chatkit import upload_chatkit_file

    storage_base = tmp_path / "chatkit_storage"

    class FakeSettings:
        def get(self, key: str, default: object | None = None) -> object | None:
            if key == "CHATKIT_STORAGE_PATH":
                return str(storage_base)
            return default

    monkeypatch.setattr("orcheo.config.get_settings", lambda: FakeSettings())

    mock_store = MagicMock()
    # Make save_attachment raise an exception
    mock_store.save_attachment = AsyncMock(side_effect=RuntimeError("Storage failed"))
    mock_server = MagicMock()
    mock_server.store = mock_store

    with patch(
        "orcheo_backend.app.routers.chatkit._resolve_chatkit_server",
        return_value=mock_server,
    ):
        file_content = b"Test content"
        headers = Headers({"content-type": "text/plain"})
        upload_file = UploadFile(
            file=BytesIO(file_content), filename="test.txt", headers=headers
        )
        mock_request = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await upload_chatkit_file(upload_file, mock_request)

        assert exc_info.value.status_code == 500
        assert "processing_error" in exc_info.value.detail["code"]  # type: ignore[index]
        assert "Failed to process file upload" in exc_info.value.detail["message"]  # type: ignore[index]


@pytest.mark.asyncio
async def test_upload_chatkit_file_invalid_encoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test file upload rejects binary files with invalid encoding.

    Note: latin-1 can decode any byte sequence, so we mock the decode to simulate
    a scenario where both UTF-8 and latin-1 decoding fail.
    """
    from fastapi import HTTPException
    from orcheo_backend.app.routers.chatkit import upload_chatkit_file

    storage_base = tmp_path / "chatkit_storage"

    class FakeSettings:
        def get(self, key: str, default: object | None = None) -> object | None:
            if key == "CHATKIT_STORAGE_PATH":
                return str(storage_base)
            return default

    monkeypatch.setattr("orcheo.config.get_settings", lambda: FakeSettings())

    mock_store = MagicMock()
    mock_store.save_attachment = AsyncMock()
    mock_server = MagicMock()
    mock_server.store = mock_store

    # Create a custom bytes-like object that raises UnicodeDecodeError
    class BadBytes(bytes):
        """Custom bytes class that fails both UTF-8 and latin-1 decoding."""

        def decode(self, encoding: str = "utf-8", errors: str = "strict") -> str:
            raise UnicodeDecodeError(
                encoding, self, 0, len(self), "test encoding error"
            )

    file_content = BadBytes([0xFF, 0xFE, 0x00, 0x00])

    # Create an UploadFile that returns our BadBytes
    class BadUploadFile(UploadFile):
        async def read(self, size: int = -1) -> bytes:
            return file_content  # type: ignore[return-value]

    with patch(
        "orcheo_backend.app.routers.chatkit._resolve_chatkit_server",
        return_value=mock_server,
    ):
        headers = Headers({"content-type": "application/octet-stream"})
        upload_file = BadUploadFile(
            file=BytesIO(b"dummy"), filename="binary.bin", headers=headers
        )
        mock_request = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await upload_chatkit_file(upload_file, mock_request)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail.get("code") == "chatkit.upload.invalid_encoding"
        assert "must be a text file" in exc_info.value.detail.get("message", "")


def test_build_inputs_payload_with_non_standard_attachments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test build_inputs_payload with invalid attachment types."""

    class FakeSettings:
        def get(self, key: str, default: object | None = None) -> object | None:
            return default

    monkeypatch.setattr(chatkit_messages, "get_settings", lambda: FakeSettings())

    thread = ThreadMetadata(
        id="thr_non_standard",
        created_at=datetime.now(UTC),
        metadata={},
    )

    # Create a user_item with attachments that are neither dict nor AttachmentBase
    user_item = MagicMock()
    user_item.attachments = [
        "string_attachment",  # Not a dict or AttachmentBase
        123,  # Not a dict or AttachmentBase
        None,  # Not a dict or AttachmentBase
    ]

    payload = build_inputs_payload(thread, "Test", [], user_item)

    # Since none of the attachments are valid types, documents list should not be added
    assert "documents" not in payload


def test_build_inputs_payload_with_mixed_valid_invalid_attachments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test build_inputs_payload filters invalid attachments."""

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
        id="thr_mixed_valid_invalid",
        created_at=datetime.now(UTC),
        metadata={},
    )

    # Mix valid and invalid attachment types
    user_item = MagicMock()
    user_item.attachments = [
        "invalid_string",  # Invalid type - should be skipped
        {
            "content": "Valid dict attachment",
            "filename": "valid.txt",
            "content_type": "text/plain",
            "size": 50,
            "file_id": "file_abc",
        },  # Valid dict
        None,  # Invalid type - should be skipped
        FileAttachment(
            id="atc789",
            name="valid_file.txt",
            mime_type="text/plain",
        ),  # Valid AttachmentBase
        12345,  # Invalid type - should be skipped
    ]

    payload = build_inputs_payload(thread, "Test", [], user_item)

    # Should only include the two valid attachments
    assert "documents" in payload
    documents = payload["documents"]
    assert len(documents) == 2
    assert documents[0]["content"] == "Valid dict attachment"
    assert documents[0]["source"] == "valid.txt"
    assert documents[1]["storage_path"] == str(storage_base / "atc789_valid_file.txt")
    assert documents[1]["source"] == "valid_file.txt"

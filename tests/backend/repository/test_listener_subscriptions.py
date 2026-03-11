from __future__ import annotations
import pytest
from orcheo.listeners import (
    ListenerCursor,
    ListenerDispatchMessage,
    ListenerDispatchPayload,
    ListenerSubscriptionStatus,
)
from orcheo_backend.app.repository import WorkflowRepository


def _listener_graph(*listeners: dict[str, object]) -> dict[str, object]:
    return {
        "nodes": [],
        "edges": [],
        "index": {"listeners": list(listeners)},
    }


@pytest.mark.asyncio()
async def test_create_version_syncs_listener_subscriptions(
    repository: WorkflowRepository,
) -> None:
    workflow = await repository.create_workflow(
        name="Listener Flow",
        slug=None,
        description=None,
        tags=None,
        actor="author",
    )

    await repository.create_version(
        workflow.id,
        graph=_listener_graph(
            {
                "node_name": "telegram_listener",
                "platform": "telegram",
                "token": "[[telegram_one]]",
                "allowed_updates": ["message"],
                "allowed_chat_types": ["private"],
                "poll_timeout_seconds": 30,
            }
        ),
        metadata={},
        notes=None,
        created_by="author",
    )

    subscriptions = await repository.list_listener_subscriptions(
        workflow_id=workflow.id
    )
    assert len(subscriptions) == 1
    assert subscriptions[0].node_name == "telegram_listener"
    assert subscriptions[0].bot_identity_key == "telegram:[[telegram_one]]"


@pytest.mark.asyncio()
async def test_dispatch_listener_event_creates_listener_run(
    repository: WorkflowRepository,
) -> None:
    workflow = await repository.create_workflow(
        name="Dispatch Flow",
        slug=None,
        description=None,
        tags=None,
        actor="author",
    )
    version = await repository.create_version(
        workflow.id,
        graph=_listener_graph(
            {
                "node_name": "telegram_listener",
                "platform": "telegram",
                "token": "[[telegram_one]]",
            }
        ),
        metadata={},
        notes=None,
        created_by="author",
    )
    subscription = (
        await repository.list_listener_subscriptions(workflow_id=workflow.id)
    )[0]

    run = await repository.dispatch_listener_event(
        subscription.id,
        ListenerDispatchPayload(
            platform="telegram",
            event_type="message",
            dedupe_key="telegram:1",
            bot_identity=subscription.bot_identity_key,
            message=ListenerDispatchMessage(chat_id="123", text="hello"),
            reply_target={"chat_id": "123"},
            raw_event={"update_id": 1},
        ),
    )

    assert run is not None
    assert run.triggered_by == "listener"
    assert run.workflow_version_id == version.id
    assert run.input_payload["listener"]["reply_target"]["chat_id"] == "123"

    duplicate = await repository.dispatch_listener_event(
        subscription.id,
        ListenerDispatchPayload(
            platform="telegram",
            event_type="message",
            dedupe_key="telegram:1",
            bot_identity=subscription.bot_identity_key,
            message=ListenerDispatchMessage(chat_id="123", text="hello"),
            reply_target={"chat_id": "123"},
            raw_event={"update_id": 1},
        ),
    )
    assert duplicate is None


@pytest.mark.asyncio()
async def test_listener_cursor_round_trip(repository: WorkflowRepository) -> None:
    workflow = await repository.create_workflow(
        name="Cursor Flow",
        slug=None,
        description=None,
        tags=None,
        actor="author",
    )
    await repository.create_version(
        workflow.id,
        graph=_listener_graph(
            {
                "node_name": "telegram_listener",
                "platform": "telegram",
                "token": "[[telegram_one]]",
            }
        ),
        metadata={},
        notes=None,
        created_by="author",
    )
    subscription = (
        await repository.list_listener_subscriptions(workflow_id=workflow.id)
    )[0]

    saved = await repository.save_listener_cursor(
        ListenerCursor(subscription_id=subscription.id, telegram_offset=42)
    )
    fetched = await repository.get_listener_cursor(subscription.id)

    assert saved.telegram_offset == 42
    assert fetched is not None
    assert fetched.telegram_offset == 42


@pytest.mark.asyncio()
async def test_archive_workflow_disables_listener_subscriptions(
    repository: WorkflowRepository,
) -> None:
    workflow = await repository.create_workflow(
        name="Archive Listener Flow",
        slug=None,
        description=None,
        tags=None,
        actor="author",
    )
    await repository.create_version(
        workflow.id,
        graph=_listener_graph(
            {
                "node_name": "telegram_listener",
                "platform": "telegram",
                "token": "[[telegram_one]]",
            }
        ),
        metadata={},
        notes=None,
        created_by="author",
    )
    subscription = (
        await repository.list_listener_subscriptions(workflow_id=workflow.id)
    )[0]

    archived = await repository.archive_workflow(workflow.id, actor="author")
    assert archived.is_archived is True

    disabled_subscription = await repository.get_listener_subscription(subscription.id)
    assert disabled_subscription.status == ListenerSubscriptionStatus.DISABLED
    assert disabled_subscription.assigned_runtime is None
    assert disabled_subscription.lease_expires_at is None

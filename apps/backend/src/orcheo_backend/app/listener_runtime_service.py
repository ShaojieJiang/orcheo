"""Lifecycle management for in-process private listener runtimes."""

from __future__ import annotations
import asyncio
import logging
from typing import Any, cast
from uuid import uuid4
from orcheo.listeners import (
    ListenerSubscription,
    ListenerSupervisor,
)
from orcheo.listeners.registry import listener_registry, register_builtin_listeners
from orcheo.models import CredentialAccessContext
from orcheo.plugins import ensure_plugins_loaded
from orcheo.runtime.credentials import CredentialResolver, parse_credential_reference
from orcheo.vault import BaseCredentialVault
from orcheo_backend.app.listener_runtime import ListenerRuntimeStore
from orcheo_backend.app.repository import WorkflowRepository


logger = logging.getLogger(__name__)

DEFAULT_LISTENER_RECONCILE_INTERVAL_SECONDS = 5.0
DEFAULT_LISTENER_HEALTH_PUBLISH_INTERVAL_SECONDS = 1.0


def resolve_listener_subscription_credentials(
    subscription: ListenerSubscription,
    *,
    vault: BaseCredentialVault,
) -> ListenerSubscription:
    """Return a subscription copy with credential placeholders materialized."""
    resolver = CredentialResolver(
        vault,
        context=CredentialAccessContext(workflow_id=subscription.workflow_id),
    )
    return subscription.model_copy(
        update={"config": _resolve_value(subscription.config, resolver)}
    )


def _resolve_value(value: Any, resolver: CredentialResolver) -> Any:
    if isinstance(value, str):
        reference = parse_credential_reference(value)
        if reference is None:
            return value
        return resolver.resolve(reference)
    if isinstance(value, list):
        return [_resolve_value(item, resolver) for item in value]
    if isinstance(value, dict):
        return {str(key): _resolve_value(item, resolver) for key, item in value.items()}
    return value


class ListenerRuntimeService:
    """Run and monitor workflow listener subscriptions inside one backend process."""

    def __init__(
        self,
        *,
        repository: WorkflowRepository,
        vault: BaseCredentialVault,
        runtime_store: ListenerRuntimeStore,
        runtime_id: str | None = None,
        reconcile_interval_seconds: float | None = None,
        health_publish_interval_seconds: float | None = None,
    ) -> None:
        """Initialize a runtime service bound to one backend process."""
        resolved_reconcile_interval = (
            reconcile_interval_seconds
            if reconcile_interval_seconds is not None
            else DEFAULT_LISTENER_RECONCILE_INTERVAL_SECONDS
        )
        resolved_health_interval = (
            health_publish_interval_seconds
            if health_publish_interval_seconds is not None
            else DEFAULT_LISTENER_HEALTH_PUBLISH_INTERVAL_SECONDS
        )
        self._repository = repository
        self._vault = vault
        self._runtime_store = runtime_store
        self._runtime_id = runtime_id or f"listener-runtime-{uuid4()}"
        self._health_publish_interval_seconds = resolved_health_interval
        self._stop_event = asyncio.Event()
        self._supervisor = ListenerSupervisor(
            repository=repository,
            runtime_id=self._runtime_id,
            adapter_factory=self._build_adapter,
            reconcile_interval_seconds=resolved_reconcile_interval,
        )
        self._serve_task: asyncio.Task[None] | None = None
        self._health_task: asyncio.Task[None] | None = None

    @property
    def runtime_id(self) -> str:
        """Return the stable runtime identifier for this process."""
        return self._runtime_id

    async def start(self) -> None:
        """Start background reconciliation and health publication loops."""
        if self._serve_task is not None or self._health_task is not None:
            return
        logger.info("Starting listener runtime %s", self._runtime_id)
        self._runtime_store.clear()
        self._serve_task = asyncio.create_task(
            self._run_supervisor(),
            name=f"{self._runtime_id}-supervisor",
        )
        self._health_task = asyncio.create_task(
            self._publish_health_loop(),
            name=f"{self._runtime_id}-health",
        )

    async def stop(self) -> None:
        """Stop background tasks and clear published health snapshots."""
        self._stop_event.set()
        tasks = [task for task in (self._serve_task, self._health_task) if task]
        for task in tasks:
            if not task.done():
                task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._serve_task = None
        self._health_task = None
        self._runtime_store.clear()
        logger.info("Stopped listener runtime %s", self._runtime_id)

    def _build_adapter(self, subscription: ListenerSubscription) -> Any:
        register_builtin_listeners()
        ensure_plugins_loaded()
        resolved = resolve_listener_subscription_credentials(
            subscription,
            vault=self._vault,
        )
        return listener_registry.build_adapter(
            resolved.platform,
            repository=cast(Any, self._repository),
            subscription=resolved,
            runtime_id=self._runtime_id,
        )

    async def _run_supervisor(self) -> None:
        try:
            await self._supervisor.serve(self._stop_event)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Listener runtime %s crashed", self._runtime_id)
            raise

    async def _publish_health_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                self._runtime_store.replace_all(self._supervisor.health())
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self._health_publish_interval_seconds,
                    )
                except TimeoutError:
                    continue
            self._runtime_store.replace_all(self._supervisor.health())
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Listener runtime %s failed while publishing health",
                self._runtime_id,
            )
            raise


__all__ = [
    "DEFAULT_LISTENER_HEALTH_PUBLISH_INTERVAL_SECONDS",
    "DEFAULT_LISTENER_RECONCILE_INTERVAL_SECONDS",
    "ListenerRuntimeService",
    "resolve_listener_subscription_credentials",
]

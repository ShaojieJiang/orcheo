"""FastAPI application entrypoint for the Orcheo backend service."""

from __future__ import annotations
import sys
from types import ModuleType
from typing import Any
from pydantic import TypeAdapter as _PydanticTypeAdapter
import orcheo_backend.app.dependencies as _dependencies_module
import orcheo_backend.app.workflow_execution as _workflow_execution_module
from orcheo.config import get_settings
from orcheo.graph.builder import build_graph
from orcheo.persistence import create_checkpointer
from orcheo_backend.app.authentication import (
    authenticate_request,
    authenticate_websocket,
)
from orcheo_backend.app.chatkit_runtime import (
    _CHATKIT_CLEANUP_INTERVAL_SECONDS,
    _chatkit_cleanup_task,
    _chatkit_server_ref,
    _coerce_int,
    get_chatkit_server,
)
from orcheo_backend.app.chatkit_runtime import (
    cancel_chatkit_cleanup_task as _cancel_chatkit_cleanup_task,
)
from orcheo_backend.app.chatkit_runtime import (
    chatkit_retention_days as _chatkit_retention_days,
)
from orcheo_backend.app.chatkit_runtime import (
    ensure_chatkit_cleanup_task as _ensure_chatkit_cleanup_task,
)
from orcheo_backend.app.chatkit_runtime import (
    get_chatkit_store as _get_chatkit_store,
)
from orcheo_backend.app.credential_utils import (
    alert_to_response as _alert_to_response,
)
from orcheo_backend.app.credential_utils import (
    build_oauth_tokens as _build_oauth_tokens,
)
from orcheo_backend.app.credential_utils import (
    build_policy as _build_policy,
)
from orcheo_backend.app.credential_utils import (
    build_scope as _build_scope,
)
from orcheo_backend.app.credential_utils import (
    credential_to_response as _credential_to_response,
)
from orcheo_backend.app.credential_utils import (
    infer_credential_access as _infer_credential_access,
)
from orcheo_backend.app.credential_utils import (
    policy_to_payload as _policy_to_payload,
)
from orcheo_backend.app.credential_utils import (
    scope_from_access as _scope_from_access,
)
from orcheo_backend.app.credential_utils import (
    scope_to_payload as _scope_to_payload,
)
from orcheo_backend.app.credential_utils import (
    template_to_response as _template_to_response,
)
from orcheo_backend.app.dependencies import (
    _create_repository,
    _credential_service_ref,
    _ensure_credential_service,
    _get_repository,
    _history_store_ref,
    _repository_ref,
    _vault_ref,
    get_credential_service,
    get_repository,
    get_vault,
)
from orcheo_backend.app.dependencies import (
    credential_context_from_workflow as _context_from_workflow,
)
from orcheo_backend.app.errors import (
    raise_conflict as _raise_conflict,
)
from orcheo_backend.app.errors import (
    raise_not_found as _raise_not_found,
)
from orcheo_backend.app.errors import (
    raise_scope_error as _raise_scope_error,
)
from orcheo_backend.app.errors import (
    raise_webhook_error as _raise_webhook_error,
)
from orcheo_backend.app.factory import create_app
from orcheo_backend.app.history_utils import (
    health_report_to_response as _health_report_to_response,
)
from orcheo_backend.app.history_utils import (
    history_to_response as _history_to_response,
)
from orcheo_backend.app.providers import (
    create_vault as _create_vault,
)
from orcheo_backend.app.providers import (
    ensure_file_vault_key as _ensure_file_vault_key,
)
from orcheo_backend.app.providers import (
    settings_value as _settings_value,
)
from orcheo_backend.app.routers import (
    chatkit as _chatkit_routes,
)
from orcheo_backend.app.routers import (
    credential_alerts as _credential_alerts_routes,
)
from orcheo_backend.app.routers import (
    credential_health as _credential_health_routes,
)
from orcheo_backend.app.routers import (
    credential_templates as _credential_templates_routes,
)
from orcheo_backend.app.routers import (
    credentials as _credentials_routes,
)
from orcheo_backend.app.routers import (
    nodes as _nodes_routes,
)
from orcheo_backend.app.routers import (
    runs as _runs_routes,
)
from orcheo_backend.app.routers import (
    triggers as _triggers_routes,
)
from orcheo_backend.app.routers import (
    workflows as _workflows_routes,
)
from orcheo_backend.app.routers.websocket import workflow_websocket
from orcheo_backend.app.workflow_execution import (
    _log_final_state_debug,
    _log_sensitive_debug,
    _log_step_debug,
    _should_log_sensitive_debug,
    execute_workflow,
)
from orcheo_backend.app.workflow_execution import logger as workflow_logger


TypeAdapter = _PydanticTypeAdapter


app = create_app()

chatkit_gateway = _chatkit_routes.chatkit_gateway
create_chatkit_session_endpoint = _chatkit_routes.create_chatkit_session_endpoint
trigger_chatkit_workflow = _chatkit_routes.trigger_chatkit_workflow
_resolve_chatkit_workspace_id = _chatkit_routes._resolve_chatkit_workspace_id

list_credentials = _credentials_routes.list_credentials
create_credential = _credentials_routes.create_credential
delete_credential = _credentials_routes.delete_credential

list_credential_templates = _credential_templates_routes.list_credential_templates
create_credential_template = _credential_templates_routes.create_credential_template
get_credential_template = _credential_templates_routes.get_credential_template
update_credential_template = _credential_templates_routes.update_credential_template
delete_credential_template = _credential_templates_routes.delete_credential_template
issue_credential_from_template = (
    _credential_templates_routes.issue_credential_from_template
)

list_governance_alerts = _credential_alerts_routes.list_governance_alerts
acknowledge_governance_alert = _credential_alerts_routes.acknowledge_governance_alert

get_workflow_credential_health = (
    _credential_health_routes.get_workflow_credential_health
)
validate_workflow_credentials = _credential_health_routes.validate_workflow_credentials

list_workflows = _workflows_routes.list_workflows
create_workflow = _workflows_routes.create_workflow
get_workflow = _workflows_routes.get_workflow
update_workflow = _workflows_routes.update_workflow
archive_workflow = _workflows_routes.archive_workflow
create_workflow_version = _workflows_routes.create_workflow_version
ingest_workflow_version = _workflows_routes.ingest_workflow_version
list_workflow_versions = _workflows_routes.list_workflow_versions
get_workflow_version = _workflows_routes.get_workflow_version
diff_workflow_versions = _workflows_routes.diff_workflow_versions

create_workflow_run = _runs_routes.create_workflow_run
list_workflow_runs = _runs_routes.list_workflow_runs
get_workflow_run = _runs_routes.get_workflow_run
list_workflow_execution_histories = _runs_routes.list_workflow_execution_histories
get_execution_history = _runs_routes.get_execution_history
replay_execution = _runs_routes.replay_execution
mark_run_started = _runs_routes.mark_run_started
mark_run_succeeded = _runs_routes.mark_run_succeeded
mark_run_failed = _runs_routes.mark_run_failed
mark_run_cancelled = _runs_routes.mark_run_cancelled

configure_webhook_trigger = _triggers_routes.configure_webhook_trigger
get_webhook_trigger_config = _triggers_routes.get_webhook_trigger_config
invoke_webhook_trigger = _triggers_routes.invoke_webhook_trigger
dispatch_cron_triggers = _triggers_routes.dispatch_cron_triggers
dispatch_manual_runs = _triggers_routes.dispatch_manual_runs
configure_cron_trigger = _triggers_routes.configure_cron_trigger
get_cron_trigger_config = _triggers_routes.get_cron_trigger_config

execute_node_endpoint = _nodes_routes.execute_node_endpoint

logger = workflow_logger

__all__ = [
    "app",
    "create_app",
    "execute_workflow",
    "get_repository",
    "get_credential_service",
    "get_vault",
    "get_chatkit_server",
    "get_settings",
    "chatkit_gateway",
    "create_chatkit_session_endpoint",
    "trigger_chatkit_workflow",
    "logger",
    "authenticate_request",
    "authenticate_websocket",
    "create_checkpointer",
    "build_graph",
    "TypeAdapter",
    "_alert_to_response",
    "_build_oauth_tokens",
    "_build_policy",
    "_build_scope",
    "_cancel_chatkit_cleanup_task",
    "_chatkit_cleanup_task",
    "_chatkit_retention_days",
    "_chatkit_server_ref",
    "_CHATKIT_CLEANUP_INTERVAL_SECONDS",
    "_coerce_int",
    "_context_from_workflow",
    "_credential_service_ref",
    "_credential_to_response",
    "_create_repository",
    "_create_vault",
    "_ensure_chatkit_cleanup_task",
    "_ensure_credential_service",
    "_ensure_file_vault_key",
    "_get_chatkit_store",
    "_get_repository",
    "_health_report_to_response",
    "_history_store_ref",
    "_history_to_response",
    "_infer_credential_access",
    "_log_final_state_debug",
    "_log_sensitive_debug",
    "_log_step_debug",
    "_policy_to_payload",
    "_settings_value",
    "_raise_conflict",
    "_raise_not_found",
    "_raise_scope_error",
    "_raise_webhook_error",
    "_repository_ref",
    "_scope_from_access",
    "_scope_to_payload",
    "_should_log_sensitive_debug",
    "_template_to_response",
    "_vault_ref",
    "_resolve_chatkit_workspace_id",
    "list_credentials",
    "create_credential",
    "delete_credential",
    "list_credential_templates",
    "create_credential_template",
    "get_credential_template",
    "update_credential_template",
    "delete_credential_template",
    "issue_credential_from_template",
    "list_governance_alerts",
    "acknowledge_governance_alert",
    "get_workflow_credential_health",
    "validate_workflow_credentials",
    "list_workflows",
    "create_workflow",
    "get_workflow",
    "update_workflow",
    "archive_workflow",
    "create_workflow_version",
    "ingest_workflow_version",
    "list_workflow_versions",
    "get_workflow_version",
    "diff_workflow_versions",
    "create_workflow_run",
    "list_workflow_runs",
    "get_workflow_run",
    "list_workflow_execution_histories",
    "get_execution_history",
    "replay_execution",
    "mark_run_started",
    "mark_run_succeeded",
    "mark_run_failed",
    "mark_run_cancelled",
    "configure_webhook_trigger",
    "get_webhook_trigger_config",
    "configure_cron_trigger",
    "get_cron_trigger_config",
    "invoke_webhook_trigger",
    "dispatch_cron_triggers",
    "dispatch_manual_runs",
    "execute_node_endpoint",
    "workflow_websocket",
]


class _AppModule(ModuleType):
    def __getattr__(self, name: str) -> Any:
        if name == "_should_log_sensitive_debug":
            return _workflow_execution_module._should_log_sensitive_debug
        return super().__getattr__(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_should_log_sensitive_debug":
            _workflow_execution_module._should_log_sensitive_debug = value
            return
        if name in {
            "_history_store_ref",
            "_repository_ref",
            "_credential_service_ref",
            "_vault_ref",
            "_create_vault",
        }:
            setattr(_dependencies_module, name, value)
            super().__setattr__(name, value)
            return
        super().__setattr__(name, value)


sys.modules[__name__].__class__ = _AppModule


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

"""Helpers for customizing the :mod:`orcheo_backend.app` module at runtime."""

from __future__ import annotations
import sys
from types import ModuleType
from typing import Any
import orcheo_backend.app.dependencies as _dependencies_module
import orcheo_backend.app.workflow_execution as _workflow_execution_module


class _AppModule(ModuleType):
    """Proxy module that mirrors selected attributes into other modules."""

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


def install_app_module_proxy(target_module_name: str) -> None:
    """Ensure the given module uses :class:`_AppModule` for getattr/setattr."""
    module = sys.modules[target_module_name]
    if isinstance(module, _AppModule):
        return

    module.__class__ = _AppModule

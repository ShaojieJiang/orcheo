"""High level Python client for talking to the Orcheo backend."""

from __future__ import annotations
from collections.abc import Callable, Mapping, MutableMapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Literal
import httpx
from httpx import Response
from orcheo_sdk.workflow import DeploymentRequest, Workflow


@dataclass(slots=True)
class OrcheoClient:
    """Lightweight helper for composing Orcheo backend requests.

    The class focuses on URL generation and payload preparation so that
    downstream applications can plug in their preferred HTTP/WebSocket stack
    (e.g. `httpx`, `aiohttp`, or the standard library).
    """

    base_url: str
    default_headers: MutableMapping[str, str] = field(default_factory=dict)
    request_timeout: float = 30.0

    def workflow_trigger_url(self, workflow_id: str) -> str:
        """Return the URL for triggering a workflow execution."""
        workflow_id = workflow_id.strip()
        if not workflow_id:
            msg = "workflow_id cannot be empty"
            raise ValueError(msg)
        return f"{self.base_url.rstrip('/')}/api/workflows/{workflow_id}/runs"

    def workflow_collection_url(self) -> str:
        """Return the base URL for workflow CRUD operations."""
        return f"{self.base_url.rstrip('/')}/api/workflows"

    def websocket_url(self, workflow_id: str) -> str:
        """Return the WebSocket endpoint used for live workflow streaming."""
        workflow_id = workflow_id.strip()
        if not workflow_id:
            msg = "workflow_id cannot be empty"
            raise ValueError(msg)

        if self.base_url.startswith("https://"):
            protocol = "wss://"
            host = self.base_url.removeprefix("https://")
        elif self.base_url.startswith("http://"):
            protocol = "ws://"
            host = self.base_url.removeprefix("http://")
        else:
            protocol = "ws://"
            host = self.base_url

        host = host.rstrip("/")
        return f"{protocol}{host}/ws/workflow/{workflow_id}"

    def prepare_headers(
        self, overrides: Mapping[str, str] | None = None
    ) -> dict[str, str]:
        """Merge default headers with request specific overrides."""
        merged: dict[str, str] = {**self.default_headers}
        if overrides:
            merged.update(overrides)
        return merged

    def build_payload(
        self,
        graph_config: Mapping[str, Any],
        inputs: Mapping[str, Any],
        execution_id: str | None = None,
    ) -> dict[str, Any]:
        """Return the JSON payload required by the workflow WebSocket."""
        payload: dict[str, Any] = {
            "type": "run_workflow",
            "graph_config": deepcopy(graph_config),
            "inputs": deepcopy(inputs),
        }
        if execution_id:
            payload["execution_id"] = execution_id
        return payload

    def build_deployment_request(
        self,
        workflow: Workflow,
        *,
        workflow_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> DeploymentRequest:
        """Return the HTTP request metadata for deploying a workflow."""
        url = self.workflow_collection_url()
        method: Literal["POST", "PUT"] = "POST"
        if workflow_id:
            workflow_id = workflow_id.strip()
            if not workflow_id:
                msg = "workflow_id cannot be empty"
                raise ValueError(msg)
            url = f"{url}/{workflow_id}"
            method = "PUT"

        payload = workflow.to_deployment_payload(metadata=metadata)
        merged_headers = self.prepare_headers(headers or {})
        return DeploymentRequest(
            method=method,
            url=url,
            json=payload,
            headers=merged_headers,
        )


class WorkflowExecutionError(RuntimeError):
    """Raised when the SDK fails to trigger a workflow run."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        """Initialize the execution error with optional status context."""
        super().__init__(message)
        self.status_code = status_code


def _default_sleep(delay: float) -> None:
    from time import sleep  # pragma: no cover - import for delegated sleep

    sleep(delay)  # pragma: no cover - simple delegation to time.sleep


@dataclass(slots=True)
class HttpWorkflowExecutor:
    """Synchronous helper that executes workflows via the HTTP API."""

    client: OrcheoClient
    auth_token: str | None = None
    timeout: float = 30.0
    max_retries: int = 3
    backoff_factor: float = 0.5
    transport: httpx.BaseTransport | None = None
    http_client: httpx.Client | None = field(default=None, repr=False)
    sleep: Callable[[float], None] = field(
        default=_default_sleep, repr=False, compare=False
    )
    retry_statuses: tuple[int, ...] = field(default=(500, 502, 503, 504), repr=False)

    def trigger_run(
        self,
        workflow_id: str,
        *,
        workflow_version_id: str,
        triggered_by: str,
        inputs: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Create a workflow run and return the backend payload."""
        url = self.client.workflow_trigger_url(workflow_id)
        request_headers = self._build_headers(headers)
        payload: dict[str, Any] = {
            "workflow_version_id": workflow_version_id,
            "triggered_by": triggered_by,
            "input_payload": dict(inputs or {}),
        }

        attempt = 0
        delay = self.backoff_factor
        last_exception: Exception | None = None
        while attempt <= self.max_retries:
            try:
                response = self._post(url, payload, request_headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                last_exception = exc
                status_code = exc.response.status_code
                if not self._should_retry(status_code) or attempt == self.max_retries:
                    msg = f"Failed to trigger workflow run (status {status_code})"
                    raise WorkflowExecutionError(msg, status_code=status_code) from exc
            except httpx.HTTPError as exc:
                last_exception = exc
                if attempt == self.max_retries:
                    raise WorkflowExecutionError(
                        "Failed to trigger workflow run"
                    ) from exc

            attempt += 1
            if attempt <= self.max_retries and delay > 0:
                self.sleep(delay)
                delay *= 2

        raise WorkflowExecutionError(
            "Failed to trigger workflow run"
        ) from last_exception  # pragma: no cover - defensive fallback

    def _build_headers(self, overrides: Mapping[str, str] | None) -> dict[str, str]:
        headers = self.client.prepare_headers(overrides or {})
        if self.auth_token and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def _post(
        self,
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
    ) -> Response:
        client = self.http_client
        if client is not None:
            return client.post(url, json=payload, headers=headers, timeout=self.timeout)

        request_kwargs: dict[str, Any] = {"timeout": self.timeout}
        if self.transport is not None:
            request_kwargs["transport"] = self.transport

        base_url = self.client.base_url.rstrip("/")
        request_kwargs["base_url"] = base_url
        relative_url = self._relative_url(url, base_url)

        with httpx.Client(**request_kwargs) as http_client:
            return http_client.post(relative_url, json=payload, headers=headers)

    @staticmethod
    def _relative_url(url: str, base_url: str) -> str:
        if url.startswith(base_url):
            suffix = url[len(base_url) :]
            return suffix or "/"
        return url

    def _should_retry(self, status_code: int) -> bool:
        return status_code in self.retry_statuses

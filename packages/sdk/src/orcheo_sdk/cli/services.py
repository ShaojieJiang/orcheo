"""Service layer bridging CLI commands and the Orcheo API."""

from __future__ import annotations
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from orcheo_sdk.cli.runtime import ApiError, CacheEntry, CliError, CliRuntime


@dataclass(slots=True)
class NodeRecord:
    """Node catalog entry."""

    name: str
    description: str
    category: str
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the node metadata for cache storage."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tags": list(self.tags),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> NodeRecord:
        """Create a node record from an API payload."""
        return cls(
            name=str(payload.get("name", "")),
            description=str(payload.get("description", "")),
            category=str(payload.get("category", "general")),
            tags=tuple(str(tag) for tag in payload.get("tags", []) if tag),
        )


@dataclass(slots=True)
class WorkflowSummary:
    """Summary metadata for a workflow returned by the API."""

    id: str
    name: str
    slug: str
    tags: tuple[str, ...]
    is_archived: bool
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> WorkflowSummary:
        """Instantiate a summary object from an API payload."""
        return cls(
            id=str(payload.get("id")),
            name=str(payload.get("name", "")),
            slug=str(payload.get("slug", "")),
            tags=tuple(str(tag) for tag in payload.get("tags", []) if tag),
            is_archived=bool(payload.get("is_archived", False)),
            created_at=_parse_datetime(payload.get("created_at")),
            updated_at=_parse_datetime(payload.get("updated_at")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the summary for cache storage."""
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "tags": list(self.tags),
            "is_archived": self.is_archived,
            "created_at": _iso_or_none(self.created_at),
            "updated_at": _iso_or_none(self.updated_at),
        }


@dataclass(slots=True)
class WorkflowDetail(WorkflowSummary):
    """Detailed workflow metadata including description."""

    description: str | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> WorkflowDetail:
        """Create a detail instance from an API payload."""
        summary = WorkflowSummary.from_mapping(payload)
        return cls(
            id=summary.id,
            name=summary.name,
            slug=summary.slug,
            tags=summary.tags,
            is_archived=summary.is_archived,
            created_at=summary.created_at,
            updated_at=summary.updated_at,
            description=payload.get("description"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the detail for cache storage."""
        payload = super().to_dict()
        payload["description"] = self.description
        return payload


@dataclass(slots=True)
class WorkflowVersionInfo:
    """Metadata describing a workflow version."""

    id: str
    version: int
    created_at: datetime | None
    notes: str | None
    graph: dict[str, Any]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> WorkflowVersionInfo:
        """Return a version record from an API payload."""
        graph = payload.get("graph")
        if not isinstance(graph, Mapping):
            graph = {}
        return cls(
            id=str(payload.get("id")),
            version=int(payload.get("version", 0)),
            created_at=_parse_datetime(payload.get("created_at")),
            notes=payload.get("notes"),
            graph=dict(graph),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the version for cache storage."""
        return {
            "id": self.id,
            "version": self.version,
            "created_at": _iso_or_none(self.created_at),
            "notes": self.notes,
            "graph": self.graph,
        }


@dataclass(slots=True)
class WorkflowRunInfo:
    """Metadata describing an individual workflow run."""

    id: str
    status: str
    triggered_by: str
    created_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> WorkflowRunInfo:
        """Create a run record from an API payload."""
        return cls(
            id=str(payload.get("id")),
            status=str(payload.get("status", "")),
            triggered_by=str(payload.get("triggered_by", "")),
            created_at=_parse_datetime(payload.get("created_at")),
            started_at=_parse_datetime(payload.get("started_at")),
            completed_at=_parse_datetime(payload.get("completed_at")),
        )


@dataclass(slots=True)
class CredentialRecord:
    """Rendered representation of a stored credential."""

    id: str
    name: str
    provider: str
    access: str
    status: str
    kind: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> CredentialRecord:
        """Instantiate a credential record from an API payload."""
        return cls(
            id=str(payload.get("id")),
            name=str(payload.get("name", "")),
            provider=str(payload.get("provider", "")),
            access=str(payload.get("access", "private")),
            status=str(payload.get("status", "unknown")),
            kind=str(payload.get("kind", "secret")),
        )


@dataclass(slots=True)
class CredentialTemplateRecord:
    """Representation of a credential template."""

    id: str
    name: str
    provider: str
    description: str | None
    scopes: tuple[str, ...]
    kind: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> CredentialTemplateRecord:
        """Return a template record from an API payload."""
        return cls(
            id=str(payload.get("id")),
            name=str(payload.get("name", "")),
            provider=str(payload.get("provider", "")),
            description=payload.get("description"),
            scopes=tuple(str(scope) for scope in payload.get("scopes", []) if scope),
            kind=str(payload.get("kind", "secret")),
        )


NODE_CACHE_KEY = "node_catalog"
WORKFLOW_CACHE_KEY = "workflow::{workflow_id}"


def _parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO timestamp, returning ``None`` on failure."""
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _iso_or_none(value: datetime | None) -> str | None:
    """Return the ISO string for ``value`` or ``None`` if absent."""
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def _load_node_catalog_from_registry() -> list[NodeRecord]:
    """Load node metadata from the local registry for offline usage."""
    try:
        from orcheo.nodes.registry import registry
    except Exception:  # pragma: no cover - optional dependency
        return []

    records: list[NodeRecord] = []
    try:
        metadata_iter: Iterable[Any] = registry.iter_metadata()  # type: ignore[attr-defined]
    except AttributeError:  # pragma: no cover - fallback for older registry versions
        metadata_iter = getattr(registry, "_metadata", {}).values()  # type: ignore[attr-defined]
    for metadata in metadata_iter:
        tags = getattr(metadata, "tags", []) or []
        records.append(
            NodeRecord(
                name=getattr(metadata, "name", ""),
                description=getattr(metadata, "description", ""),
                category=getattr(metadata, "category", "general"),
                tags=tuple(str(tag) for tag in tags if tag),
            )
        )
    return sorted(records, key=lambda record: record.name.lower())


def fetch_node_catalog(
    runtime: CliRuntime,
) -> tuple[list[NodeRecord], bool, CacheEntry | None]:
    """Return the node catalog, optionally sourced from cache."""
    cache = runtime.cache
    cached_entry = cache.load(NODE_CACHE_KEY)
    from_cache = runtime.offline

    if runtime.offline:
        if cached_entry is not None and isinstance(cached_entry.data, list):
            return (
                [NodeRecord.from_mapping(item) for item in cached_entry.data],
                True,
                cached_entry,
            )
        return (_load_node_catalog_from_registry(), True, None)

    api = runtime.require_api()
    payload: Any | None = None
    try:
        payload = api.get_json("/api/nodes/catalog")
    except ApiError as exc:
        if exc.status_code not in {404, 501}:
            raise
        payload = None

    records: list[NodeRecord]
    if isinstance(payload, list):
        records = [NodeRecord.from_mapping(item) for item in payload]
    else:
        records = _load_node_catalog_from_registry()

    cache.store(NODE_CACHE_KEY, [record.to_dict() for record in records])
    return (records, from_cache, cached_entry)


def fetch_workflows(runtime: CliRuntime) -> list[WorkflowSummary]:
    """Return the list of workflows available to the caller."""
    api = runtime.require_api()
    try:
        payload = api.get_json("/api/workflows")
    except ApiError as exc:  # pragma: no cover - passthrough to CLI
        raise CliError(str(exc)) from exc
    if not isinstance(payload, list):
        raise CliError("Unexpected response from the workflows endpoint")
    return [WorkflowSummary.from_mapping(item) for item in payload]


def fetch_workflow_detail(
    runtime: CliRuntime, workflow_id: str
) -> tuple[WorkflowDetail, list[WorkflowVersionInfo], CacheEntry | None]:
    """Return workflow detail, associated versions, and cached metadata."""
    cache_key = WORKFLOW_CACHE_KEY.format(workflow_id=workflow_id)
    cache = runtime.cache
    cached_entry = cache.load(cache_key)

    if runtime.offline:
        if cached_entry is None or not isinstance(cached_entry.data, Mapping):
            raise CliError(
                "Workflow details are not cached locally; "
                "re-run while online to prime the cache",
            )
        detail_payload = cached_entry.data.get("detail")
        if not isinstance(detail_payload, Mapping):
            raise CliError("Cached workflow detail payload is invalid")
        versions_payload = cached_entry.data.get("versions", [])
        if not isinstance(versions_payload, Iterable):
            raise CliError("Cached workflow versions payload is invalid")
        detail = WorkflowDetail.from_mapping(detail_payload)
        versions = [WorkflowVersionInfo.from_mapping(item) for item in versions_payload]
        return detail, versions, cached_entry

    api = runtime.require_api()
    try:
        detail_payload = api.get_json(f"/api/workflows/{workflow_id}")
        versions_payload = api.get_json(f"/api/workflows/{workflow_id}/versions")
    except ApiError as exc:  # pragma: no cover - passthrough to CLI
        raise CliError(str(exc)) from exc
    if not isinstance(detail_payload, Mapping):
        raise CliError("Unexpected workflow detail payload")
    if not isinstance(versions_payload, list):
        raise CliError("Unexpected workflow version payload")
    detail = WorkflowDetail.from_mapping(detail_payload)
    versions = [WorkflowVersionInfo.from_mapping(item) for item in versions_payload]
    cache.store(
        cache_key,
        {
            "detail": detail.to_dict(),
            "versions": [version.to_dict() for version in versions],
        },
    )
    return detail, versions, cached_entry


def fetch_workflow_runs(runtime: CliRuntime, workflow_id: str) -> list[WorkflowRunInfo]:
    """Return workflow run metadata, or ``[]`` when offline."""
    if runtime.offline:
        return []
    api = runtime.require_api()
    try:
        payload = api.get_json(f"/api/workflows/{workflow_id}/runs")
    except ApiError as exc:  # pragma: no cover - passthrough to CLI
        raise CliError(str(exc)) from exc
    if not isinstance(payload, list):
        raise CliError("Unexpected workflow run payload")
    return [WorkflowRunInfo.from_mapping(item) for item in payload]


def trigger_workflow_run(
    runtime: CliRuntime,
    *,
    workflow_id: str,
    workflow_version_id: str,
    actor: str,
    inputs: Mapping[str, Any] | None = None,
) -> WorkflowRunInfo:
    """Trigger a workflow run and return its metadata."""
    api = runtime.require_api()
    payload = {
        "workflow_version_id": workflow_version_id,
        "triggered_by": actor,
        "input_payload": dict(inputs or {}),
    }
    try:
        response = api.post_json(
            f"/api/workflows/{workflow_id}/runs",
            json_payload=payload,
        )
    except ApiError as exc:  # pragma: no cover - passthrough to CLI
        raise CliError(str(exc)) from exc
    if not isinstance(response, Mapping):
        raise CliError("Unexpected workflow run response")
    return WorkflowRunInfo.from_mapping(response)


def fetch_credentials(
    runtime: CliRuntime,
    *,
    workflow_id: str | None = None,
) -> list[CredentialRecord]:
    """Return credential metadata optionally filtered by workflow."""
    api = runtime.require_api()
    params = {"workflow_id": workflow_id} if workflow_id else None
    try:
        payload = api.get_json("/api/credentials", params=params)
    except ApiError as exc:  # pragma: no cover - passthrough to CLI
        raise CliError(str(exc)) from exc
    if not isinstance(payload, list):
        raise CliError("Unexpected credential response")
    return [CredentialRecord.from_mapping(item) for item in payload]


def fetch_credential_templates(runtime: CliRuntime) -> list[CredentialTemplateRecord]:
    """Return credential templates available to the caller."""
    api = runtime.require_api()
    try:
        payload = api.get_json("/api/credentials/templates")
    except ApiError as exc:  # pragma: no cover - passthrough to CLI
        raise CliError(str(exc)) from exc
    if not isinstance(payload, list):
        raise CliError("Unexpected credential template response")
    return [CredentialTemplateRecord.from_mapping(item) for item in payload]


def issue_credential(
    runtime: CliRuntime,
    *,
    template_id: str,
    secret: str,
    actor: str,
    name: str | None = None,
    scopes: list[str] | None = None,
    workflow_id: str | None = None,
) -> Mapping[str, Any]:
    """Issue a credential from a stored template."""
    api = runtime.require_api()
    payload: dict[str, Any] = {
        "template_id": template_id,
        "secret": secret,
        "actor": actor,
    }
    if name:
        payload["name"] = name
    if scopes is not None:
        payload["scopes"] = scopes
    if workflow_id:
        payload["workflow_id"] = workflow_id
    try:
        response = api.post_json(
            f"/api/credentials/templates/{template_id}/issue",
            json_payload=payload,
        )
    except ApiError as exc:  # pragma: no cover - passthrough to CLI
        raise CliError(str(exc)) from exc
    if not isinstance(response, Mapping):
        raise CliError("Unexpected response while issuing credential")
    return response


def delete_credential(
    runtime: CliRuntime,
    credential_id: str,
    *,
    workflow_id: str | None = None,
) -> None:
    """Delete a credential from the vault."""
    api = runtime.require_api()
    path = f"/api/credentials/{credential_id}"
    if workflow_id:
        path = f"{path}?workflow_id={workflow_id}"
    try:
        api.delete(path)
    except ApiError as exc:  # pragma: no cover - passthrough to CLI
        raise CliError(str(exc)) from exc

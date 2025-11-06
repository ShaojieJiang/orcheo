"""Tests for `_infer_credential_access` helper."""

from __future__ import annotations
from uuid import uuid4
from orcheo.models import CredentialScope
from orcheo_backend.app import _infer_credential_access


def test_infer_credential_access_public() -> None:
    """Credential access inference returns 'public' for unrestricted scopes."""

    scope = CredentialScope()
    label = _infer_credential_access(scope)

    assert label == "public"


def test_infer_credential_access_private_single_workflow() -> None:
    """Credential access inference returns 'private' for single workflow restriction."""

    scope = CredentialScope(workflow_ids=[uuid4()])
    label = _infer_credential_access(scope)

    assert label == "private"


def test_infer_credential_access_private_single_workspace() -> None:
    """Credential access returns 'private' for single workspace restriction."""

    scope = CredentialScope(workspace_ids=[uuid4()])
    label = _infer_credential_access(scope)

    assert label == "private"


def test_infer_credential_access_private_single_role() -> None:
    """Credential access inference returns 'private' for single role restriction."""

    scope = CredentialScope(roles=["admin"])
    label = _infer_credential_access(scope)

    assert label == "private"


def test_infer_credential_access_shared_multiple_workflows() -> None:
    """Credential access returns 'shared' for multiple workflow restrictions."""

    scope = CredentialScope(workflow_ids=[uuid4(), uuid4()])
    label = _infer_credential_access(scope)

    assert label == "shared"


def test_infer_credential_access_shared_mixed_restrictions() -> None:
    """Credential access returns 'shared' when mixing identifiers."""

    scope = CredentialScope(workflow_ids=[uuid4()], workspace_ids=[uuid4()])
    label = _infer_credential_access(scope)

    assert label == "shared"

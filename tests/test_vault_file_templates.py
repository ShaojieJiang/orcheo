"""Template and alert tests for FileCredentialVault."""

from __future__ import annotations
from uuid import uuid4
import pytest
from orcheo.models import (
    AesGcmCredentialCipher,
    GovernanceAlertKind,
    SecretGovernanceAlertSeverity,
)
from orcheo.vault import (
    CredentialTemplateNotFoundError,
    FileCredentialVault,
    GovernanceAlertNotFoundError,
)


def test_file_vault_manages_templates_and_alerts(tmp_path) -> None:
    cipher = AesGcmCredentialCipher(key="file-template")
    vault_path = tmp_path / "vault.sqlite"
    vault = FileCredentialVault(vault_path, cipher=cipher)
    template = vault.create_template(
        name="GitHub",
        provider="github",
        scopes=["repo"],
        actor="alice",
        kind="secret",
    )
    reloaded = FileCredentialVault(vault_path, cipher=cipher)
    listed = reloaded.list_templates()
    assert [item.id for item in listed] == [template.id]
    fetched = reloaded.get_template(template_id=template.id)
    assert fetched.name == "GitHub"

    credential = reloaded.create_credential(
        name="GitHub",
        provider="github",
        scopes=["repo"],
        secret="tok",
        actor="ops",
    )
    alert = reloaded.record_alert(
        kind=GovernanceAlertKind.TOKEN_EXPIRING,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="expiring",
        actor="ops",
        credential_id=credential.id,
    )

    alerts = reloaded.list_alerts(include_acknowledged=True)
    assert [item.id for item in alerts] == [alert.id]
    acknowledged = reloaded.acknowledge_alert(alert.id, actor="ops")
    assert acknowledged.is_acknowledged

    with pytest.raises(GovernanceAlertNotFoundError):
        reloaded.acknowledge_alert(uuid4(), actor="ops")

    with pytest.raises(CredentialTemplateNotFoundError):
        reloaded.get_template(template_id=uuid4())

    reloaded.delete_template(template.id)
    with pytest.raises(CredentialTemplateNotFoundError):
        reloaded.get_template(template_id=template.id)


def test_file_vault_remove_template_missing(tmp_path) -> None:
    vault = FileCredentialVault(tmp_path / "vault.sqlite")
    with pytest.raises(CredentialTemplateNotFoundError):
        vault.delete_template(uuid4())


def test_file_vault_remove_template_direct(tmp_path) -> None:
    vault = FileCredentialVault(tmp_path / "vault.sqlite")
    with pytest.raises(CredentialTemplateNotFoundError):
        vault._remove_template(uuid4())


def test_file_vault_remove_alert_clears(tmp_path) -> None:
    cipher = AesGcmCredentialCipher(key="file-alert")
    vault = FileCredentialVault(tmp_path / "vault.sqlite", cipher=cipher)
    metadata = vault.create_credential(
        name="Service",
        provider="service",
        scopes=["read"],
        secret="secret",
        actor="ops",
    )
    alert = vault.record_alert(
        kind=GovernanceAlertKind.VALIDATION_FAILED,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="bad",
        actor="ops",
        credential_id=metadata.id,
    )

    vault._remove_alert(alert.id)

    assert vault.list_alerts() == []

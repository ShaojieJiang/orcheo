"""Aggregated schemas for FastAPI endpoints.

The legacy import path ``orcheo_backend.app.schemas`` continues to work by
re-exporting the concrete schema classes from the new modular structure.
"""

from orcheo.models import CredentialHealthStatus  # noqa: F401
from orcheo_backend.app.schemas.chatkit import (  # noqa: F401
    ChatKitSessionRequest,
    ChatKitSessionResponse,
    ChatKitWorkflowTriggerRequest,
)
from orcheo_backend.app.schemas.credentials import (  # noqa: F401
    CredentialCreateRequest,
    CredentialHealthItem,
    CredentialHealthResponse,
    CredentialIssuancePolicyPayload,
    CredentialIssuanceRequest,
    CredentialIssuanceResponse,
    CredentialScopePayload,
    CredentialTemplateCreateRequest,
    CredentialTemplateResponse,
    CredentialTemplateUpdateRequest,
    CredentialValidationRequest,
    CredentialVaultEntryResponse,
    OAuthTokenRequest,
)
from orcheo_backend.app.schemas.governance import (  # noqa: F401
    AlertAcknowledgeRequest,
    GovernanceAlertResponse,
)
from orcheo_backend.app.schemas.nodes import (  # noqa: F401
    NodeExecutionRequest,
    NodeExecutionResponse,
)
from orcheo_backend.app.schemas.runs import (  # noqa: F401
    CronDispatchRequest,
    RunActionRequest,
    RunCancelRequest,
    RunFailRequest,
    RunHistoryResponse,
    RunHistoryStepResponse,
    RunReplayRequest,
    RunSucceedRequest,
)
from orcheo_backend.app.schemas.workflows import (  # noqa: F401
    WorkflowCreateRequest,
    WorkflowRunCreateRequest,
    WorkflowUpdateRequest,
    WorkflowVersionCreateRequest,
    WorkflowVersionDiffResponse,
    WorkflowVersionIngestRequest,
)


__all__ = [
    "AlertAcknowledgeRequest",
    "ChatKitSessionRequest",
    "ChatKitSessionResponse",
    "ChatKitWorkflowTriggerRequest",
    "CronDispatchRequest",
    "CredentialCreateRequest",
    "CredentialHealthItem",
    "CredentialHealthResponse",
    "CredentialHealthStatus",
    "CredentialIssuancePolicyPayload",
    "CredentialIssuanceRequest",
    "CredentialIssuanceResponse",
    "CredentialScopePayload",
    "CredentialTemplateCreateRequest",
    "CredentialTemplateResponse",
    "CredentialTemplateUpdateRequest",
    "CredentialValidationRequest",
    "CredentialVaultEntryResponse",
    "GovernanceAlertResponse",
    "NodeExecutionRequest",
    "NodeExecutionResponse",
    "OAuthTokenRequest",
    "RunActionRequest",
    "RunCancelRequest",
    "RunFailRequest",
    "RunHistoryResponse",
    "RunHistoryStepResponse",
    "RunReplayRequest",
    "RunSucceedRequest",
    "WorkflowCreateRequest",
    "WorkflowRunCreateRequest",
    "WorkflowUpdateRequest",
    "WorkflowVersionCreateRequest",
    "WorkflowVersionDiffResponse",
    "WorkflowVersionIngestRequest",
]

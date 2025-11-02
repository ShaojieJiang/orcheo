"""Service layer for Orcheo SDK.

This module contains the core business logic for interacting with the Orcheo API.
Services are pure functions that operate on data and are reused by both CLI and
MCP interfaces.
"""

from orcheo_sdk.services.codegen import (
    generate_workflow_scaffold_data,
    generate_workflow_template_data,
)
from orcheo_sdk.services.credentials import (
    create_credential_data,
    delete_credential_data,
    get_credential_reference_data,
    list_credentials_data,
)
from orcheo_sdk.services.nodes import list_nodes_data, show_node_data
from orcheo_sdk.services.workflows import (
    delete_workflow_data,
    download_workflow_data,
    list_workflows_data,
    run_workflow_data,
    show_workflow_data,
    upload_workflow_data,
)


__all__ = [
    # Workflows
    "list_workflows_data",
    "show_workflow_data",
    "run_workflow_data",
    "delete_workflow_data",
    "upload_workflow_data",
    "download_workflow_data",
    # Nodes
    "list_nodes_data",
    "show_node_data",
    # Credentials
    "list_credentials_data",
    "create_credential_data",
    "delete_credential_data",
    "get_credential_reference_data",
    # Code generation
    "generate_workflow_scaffold_data",
    "generate_workflow_template_data",
]

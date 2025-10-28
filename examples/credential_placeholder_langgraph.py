"""Example LangGraph workflow demonstrating credential placeholders.

This example shows how to use credential placeholders in Orcheo workflows.
Credential placeholders use the [[credential_name]] syntax and are resolved
at runtime from the credential vault.
"""

from __future__ import annotations
import asyncio
from typing import Any
from langgraph.graph import END, START, StateGraph
from orcheo.graph.state import State
from orcheo.models import CredentialScope
from orcheo.nodes.logic import SetVariableNode
from orcheo.runtime.credentials import CredentialResolver, credential_resolution
from orcheo.vault import InMemoryCredentialVault


def build_graph() -> StateGraph:
    """Return a LangGraph with a credential placeholder."""
    graph = StateGraph(State)
    graph.add_node(
        "store_secret",
        SetVariableNode(
            name="store_secret",
            variables={
                # Credential placeholder - resolved at runtime from vault
                "telegram_token": "[[telegram_bot]]",
                # Multiple credentials can be used
                "api_key": "[[openai_api_key]]",
                # You can also store static values alongside credentials
                "bot_name": "MyBot",
                "enabled": True,
            },
        ),
    )
    graph.add_edge(START, "store_secret")
    graph.add_edge("store_secret", END)
    return graph


async def run_example(with_resolver: bool = True) -> dict[str, Any]:
    """Run the example workflow.

    Args:
        with_resolver: If True, use a credential resolver to resolve placeholders

    Returns:
        The final state of the workflow
    """
    graph = build_graph()
    graph.set_entry_point("store_secret")

    # Compile and run
    workflow = graph.compile()

    # Initialize state
    initial_state: State = {
        "inputs": {},
        "messages": [],
        "results": {},
    }

    # Set up credential resolver if requested
    if with_resolver:
        # Create an in-memory vault with sample credentials
        vault = InMemoryCredentialVault()

        # Add telegram bot token
        vault.create_credential(
            name="telegram_bot",
            provider="telegram",
            scopes=["bot"],
            secret="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
            actor="example_user",
            scope=CredentialScope.unrestricted(),
        )

        # Add OpenAI API key
        vault.create_credential(
            name="openai_api_key",
            provider="openai",
            scopes=["api"],
            secret="sk-proj-example_key_1234567890",
            actor="example_user",
            scope=CredentialScope.unrestricted(),
        )

        resolver = CredentialResolver(vault)

        # Execute with credential resolution enabled
        with credential_resolution(resolver):
            final_state = await workflow.ainvoke(initial_state)
    else:
        # Execute without credential resolution - will fail if placeholders exist
        final_state = await workflow.ainvoke(initial_state)

    return final_state


async def main() -> None:
    """Run examples demonstrating credential placeholder usage."""
    print("=" * 60)
    print("LangGraph Credential Placeholder Example")
    print("=" * 60)

    print("\n--- Example: With Credential Resolver ---")
    print("When a credential resolver is active, placeholders like [[telegram_bot]]")
    print("are automatically resolved from the vault at runtime.\n")

    result = await run_example(with_resolver=True)

    # Get the results from the store_secret node
    store_secret_result = result["results"].get("store_secret", {})

    print("Workflow Results:")
    print(f"  Telegram Token: {store_secret_result.get('telegram_token')}")
    print(f"  OpenAI API Key: {store_secret_result.get('api_key')}")
    print(f"  Bot Name: {store_secret_result.get('bot_name')}")
    print(f"  Enabled: {store_secret_result.get('enabled')}")

    print("\n--- Credential Placeholder Syntax ---")
    print("Credential placeholders use [[credential_name]] or")
    print("[[credential_name#payload.path]] syntax:")
    print()
    print("  [[telegram_bot]]                    -> secret field (default)")
    print("  [[telegram_bot#secret]]             -> secret field (explicit)")
    print("  [[my_oauth#oauth.access_token]]     -> OAuth access token")
    print("  [[my_oauth#oauth.refresh_token]]    -> OAuth refresh token")
    print("  [[my_oauth#oauth.expires_at]]       -> OAuth expiration time")

    print("\n" + "=" * 60)
    print("Key Points:")
    print("  1. Placeholders use [[name]] or [[name#path]] syntax")
    print("  2. Credentials are resolved from a vault at execution time")
    print("  3. Credentials can be referenced by name or UUID")
    print("  4. Different payload paths support secrets and OAuth tokens")
    print("  5. Requires credential_resolution() context manager")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

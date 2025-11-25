"""Entry point for the Conversational Search demo."""

from __future__ import annotations
from pathlib import Path
from typing import Any
from examples.conversational_search.utils import (
    default_demo_paths,
    load_demo_assets,
    summarize_dataset,
)


def _conversation_settings(config: dict[str, Any]) -> str:
    conversation = config.get("conversation", {})
    max_turns = conversation.get("max_turns", "n/a")
    memory_store = conversation.get("memory_store", "unknown")
    query_processing = config.get("query_processing", {})
    processors = ", ".join(sorted(query_processing)) or "none"
    return (
        f"conversation: max_turns={max_turns}, memory_store={memory_store}; "
        f"processors={processors}"
    )


def main() -> None:
    """Preview the Conversational Search demo configuration and dataset."""
    demo_root = Path(__file__).parent
    paths = default_demo_paths(demo_root)
    config, documents, queries = load_demo_assets(paths)

    print("Demo 3: Conversational Search")  # noqa: T201 - demo output
    print(_conversation_settings(config))  # noqa: T201 - demo output
    print(summarize_dataset(documents, queries))  # noqa: T201 - demo output


if __name__ == "__main__":
    main()

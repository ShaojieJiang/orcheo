"""Entry point for the Hybrid Search demo."""

from __future__ import annotations
from pathlib import Path
from typing import Any
from examples.conversational_search.utils import (
    default_demo_paths,
    load_demo_assets,
    summarize_dataset,
)


def _describe_retrieval(config: dict[str, Any]) -> str:
    retrieval = config.get("retrieval", {})
    branches = [
        key for key in retrieval if key not in {"fusion", "reranker", "compressor"}
    ]
    extras = [key for key in retrieval if key in {"fusion", "reranker"}]
    return (
        f"branches={', '.join(sorted(branches)) or 'none'}, "
        f"extras={', '.join(sorted(extras)) or 'none'}"
    )


def main() -> None:
    """Preview the Hybrid Search demo configuration and dataset."""
    demo_root = Path(__file__).parent
    paths = default_demo_paths(demo_root)
    config, documents, queries = load_demo_assets(paths)

    print("Demo 2: Hybrid Search")  # noqa: T201 - demo output
    print(_describe_retrieval(config))  # noqa: T201 - demo output
    print(summarize_dataset(documents, queries))  # noqa: T201 - demo output


if __name__ == "__main__":
    main()

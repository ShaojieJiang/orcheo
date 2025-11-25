"""Entry point for the Basic RAG demo."""

from __future__ import annotations
from pathlib import Path
from examples.conversational_search.utils import (
    default_demo_paths,
    load_demo_assets,
    summarize_dataset,
)


def main() -> None:
    """Preview the Basic RAG demo configuration and dataset."""
    demo_root = Path(__file__).parent
    paths = default_demo_paths(demo_root)
    config, documents, queries = load_demo_assets(paths)
    sections = ", ".join(sorted(config))

    print("Demo 1: Basic RAG")  # noqa: T201 - demo output
    print(f"Config sections: {sections}")  # noqa: T201 - demo output
    print(summarize_dataset(documents, queries))  # noqa: T201 - demo output


if __name__ == "__main__":
    main()

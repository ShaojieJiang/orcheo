"""Entry point for the Evaluation & Research demo."""

from __future__ import annotations
from pathlib import Path
from typing import Any
from examples.conversational_search.utils import (
    default_demo_paths,
    load_demo_assets,
    load_golden_examples,
    load_relevance_labels,
    summarize_dataset,
)


def _variant_summary(config: dict[str, Any]) -> str:
    variants = config.get("variants", [])
    names = [variant.get("name", "unnamed") for variant in variants]
    return f"variants={', '.join(names) or 'none'}"


def main() -> None:
    """Preview the Evaluation demo configuration and datasets."""
    demo_root = Path(__file__).parent
    paths = default_demo_paths(demo_root)
    config, documents, queries = load_demo_assets(paths)
    golden = load_golden_examples(paths.golden) if paths.golden else []
    labels = load_relevance_labels(paths.labels) if paths.labels else []

    print("Demo 5: Evaluation & Research")  # noqa: T201 - demo output
    print(_variant_summary(config))  # noqa: T201 - demo output
    print(f"Golden examples={len(golden)}, relevance labels={len(labels)}")  # noqa: T201 - demo output
    print(summarize_dataset(documents, queries))  # noqa: T201 - demo output


if __name__ == "__main__":
    main()

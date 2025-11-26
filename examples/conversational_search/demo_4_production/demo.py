"""Entry point for the Production demo."""

from __future__ import annotations
from pathlib import Path
from typing import Any
from examples.conversational_search.utils import (
    default_demo_paths,
    load_demo_assets,
    summarize_dataset,
)


def _production_toggles(config: dict[str, Any]) -> str:
    production = config.get("production", {})
    caching = production.get("caching", {})
    streaming = production.get("streaming", {})
    guardrails = production.get("guardrails", {})
    toggles = {
        "caching": caching.get("enabled", False),
        "streaming": streaming.get("enabled", False),
        "hallucination_guard": "hallucination" in guardrails,
        "policy_compliance": "policy_compliance" in guardrails,
    }
    return ", ".join(f"{key}={value}" for key, value in toggles.items())


def main() -> None:
    """Preview the Production demo configuration and dataset."""
    demo_root = Path(__file__).parent
    paths = default_demo_paths(demo_root)
    config, documents, queries = load_demo_assets(paths)

    print("Demo 4: Production Pipeline")  # noqa: T201 - demo output
    print(_production_toggles(config))  # noqa: T201 - demo output
    print(summarize_dataset(documents, queries))  # noqa: T201 - demo output


if __name__ == "__main__":
    main()

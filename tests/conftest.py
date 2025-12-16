"""Configure test environment for Orcheo."""

import os
import sys
import warnings
from pathlib import Path
import pytest


warnings.filterwarnings(
    "ignore",
    module="chatkit.widgets",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    module="chatkit.actions",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    module="typing_extensions",
    category=DeprecationWarning,
)

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import chatkit.actions  # noqa: F401
    import chatkit.types  # noqa: F401
    import chatkit.widgets  # noqa: F401


pytest_plugins = [
    "tests.backend.chatkit_router_helpers_support",
]


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "backend" / "src"
SDK_SRC = ROOT / "packages" / "sdk" / "src"
for path in (BACKEND_SRC, SDK_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture(autouse=True)
def _ensure_openai_api_key(monkeypatch):
    """Provide a deterministic OpenAI API key for tests when missing."""

    if not os.environ.get("OPENAI_API_KEY"):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-orcheo")

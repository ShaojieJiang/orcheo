"""Configure test environment for Orcheo."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "backend" / "src"
SDK_SRC = ROOT / "packages" / "sdk" / "src"

for path in (BACKEND_SRC, SDK_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

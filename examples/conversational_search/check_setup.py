#!/usr/bin/env python3
"""Quick setup checker for conversational search demos.

Run this before attempting demos to ensure prerequisites are met.
"""

import subprocess
import sys
from pathlib import Path


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def print_status(check: str, passed: bool, message: str = "") -> None:
    """Print a check result."""
    symbol = "✓" if passed else "✗"
    status = "PASS" if passed else "FAIL"
    print(f"  [{symbol}] {check}: {status}")
    if message:
        print(f"      {message}")


def check_python_version() -> bool:
    """Check if Python version is 3.12+."""
    version = sys.version_info
    if version.major == 3 and version.minor >= 12:
        print_status("Python version", True, f"Python {version.major}.{version.minor}")
        return True
    else:
        print_status(
            "Python version",
            False,
            f"Python {version.major}.{version.minor} found, need 3.12+",
        )
        return False


def check_uv_installed() -> bool:
    """Check if uv is installed."""
    try:
        result = subprocess.run(
            ["uv", "--version"], check=False, capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print_status("uv package manager", True, version)
            return True
        else:
            print_status("uv package manager", False)
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print_status(
            "uv package manager", False, "Install from: https://docs.astral.sh/uv/"
        )
        return False


def check_orcheo_cli() -> bool:
    """Check if orcheo CLI is available."""
    try:
        result = subprocess.run(
            ["orcheo", "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            print_status("Orcheo CLI", True)
            return True
        else:
            print_status("Orcheo CLI", False)
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print_status("Orcheo CLI", False, "Run: uv sync --group examples")
        return False


def check_credential(name: str) -> bool:
    """Check if a credential exists in the vault."""
    try:
        result = subprocess.run(
            ["orcheo", "credential", "get", name],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_demo_credentials() -> tuple[bool, list[str]]:
    """Check which demo credentials are configured."""
    credentials = {
        "openai_api_key": "Required for all demos",
        "tavily_api_key": "Required for Demo 3",
        "pinecone_api_key": "Required for Demos 1, 4, 5, 6",
    }

    missing = []
    for cred_name, description in credentials.items():
        exists = check_credential(cred_name)
        print_status(f"Credential: {cred_name}", exists, description)
        if not exists:
            missing.append(cred_name)

    return len(missing) == 0, missing


def check_data_directory() -> bool:
    """Check if sample data directory exists."""
    data_dir = Path(__file__).parent / "data"
    if data_dir.exists() and data_dir.is_dir():
        docs_dir = data_dir / "docs"
        queries_file = data_dir / "queries.json"
        has_docs = docs_dir.exists()
        has_queries = queries_file.exists()
        if has_docs and has_queries:
            print_status("Sample data", True, f"Found at {data_dir}")
            return True
        else:
            print_status("Sample data", False, f"Incomplete data at {data_dir}")
            return False
    else:
        print_status("Sample data", False, f"Not found at {data_dir}")
        return False


def print_quickstart_guide(missing_creds: list[str]) -> None:
    """Print next steps guide."""
    print("\n" + "─" * 60)
    print("  Next Steps")
    print("─" * 60 + "\n")

    if missing_creds:
        print("1. Create missing credentials:")
        for cred in missing_creds:
            print(f"   orcheo credential create {cred} --secret <your-key>")
        print()

    print("2. Run Demo 2 (works locally, no external DB):")
    print("   python examples/conversational_search/demo_2_basic_rag/demo_2.py")
    print()
    print("3. For other demos, see individual README files:")
    print("   examples/conversational_search/demo_<N>_*/README.md")
    print()


def main() -> int:
    """Run all checks and report status."""
    print_header("Conversational Search Demo Setup Check")

    all_passed = True

    # System checks
    if not check_python_version():
        all_passed = False

    if not check_uv_installed():
        all_passed = False

    if not check_orcheo_cli():
        all_passed = False

    # Data checks
    if not check_data_directory():
        all_passed = False

    # Credential checks
    print()
    creds_ok, missing_creds = check_demo_credentials()
    if not creds_ok:
        print(
            "\n  ⚠️  Some credentials are missing. "
            "Demo 1 requires at least openai_api_key."
        )
        all_passed = False

    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("  ✓ All checks passed! You're ready to run demos.")
    else:
        print("  ⚠️  Some checks failed. See details above.")
    print("=" * 60)

    # Next steps
    print_quickstart_guide(missing_creds)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

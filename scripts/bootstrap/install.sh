#!/usr/bin/env sh
set -eu

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

: "${ORCHEO_STACK_ASSET_BASE_URL:=https://raw.githubusercontent.com/ShaojieJiang/orcheo/main/deploy/local-stack}"
export ORCHEO_STACK_ASSET_BASE_URL

if [ "$#" -gt 0 ]; then
  exec uvx orcheo-sdk install "$@"
fi

if [ -n "${ORCHEO_INSTALL_ARGS:-}" ]; then
  # Match install.ps1 behavior: split env var by whitespace into args.
  # shellcheck disable=SC2086
  exec uvx orcheo-sdk install $ORCHEO_INSTALL_ARGS
fi

exec uvx orcheo-sdk install

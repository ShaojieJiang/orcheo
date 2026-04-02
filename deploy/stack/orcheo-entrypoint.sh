#!/bin/sh

set -eu

runtime_user="${ORCHEO_RUNTIME_USER:-orcheo}"
runtime_group="${ORCHEO_RUNTIME_GROUP:-orcheo}"
home_dir="${ORCHEO_RUNTIME_HOME:-${HOME:-/data/home}}"

if [ "$home_dir" = "/root" ]; then
  home_dir="/data/home"
fi

export HOME="$home_dir"

codex_home="${CODEX_HOME:-$HOME/.codex}"
claude_home="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
runtime_root="/data/agent-runtimes"
cache_dir="${ORCHEO_CACHE_DIR:-/data/cache/orcheo}"
plugin_dir="${ORCHEO_PLUGIN_DIR:-/data/plugins}"
uv_cache_dir="${UV_CACHE_DIR:-/data/cache/uv}"

ensure_dir() {
  dir_path="$1"
  recursive="${2:-false}"
  if [ -z "$dir_path" ]; then
    return
  fi
  mkdir -p "$dir_path"
  if [ "$recursive" = "true" ]; then
    chown -R "$runtime_user:$runtime_group" "$dir_path"
  else
    chown "$runtime_user:$runtime_group" "$dir_path"
  fi
}

if [ "$(id -u)" -eq 0 ]; then
  ensure_dir /data
  ensure_dir "$HOME" true
  ensure_dir "$codex_home" true
  ensure_dir "$claude_home" true
  ensure_dir "$runtime_root" true
  ensure_dir "$cache_dir" true
  ensure_dir "$plugin_dir" true
  ensure_dir "$uv_cache_dir" true

  if [ -d /app/.venv ] || [ ! -e /app/.venv ]; then
    ensure_dir /app/.venv true
  fi

  exec gosu "$runtime_user:$runtime_group" "$@"
fi

exec "$@"

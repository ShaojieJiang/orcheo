#!/usr/bin/env bash
# Purpose: Bootstrap an Ubuntu machine for Orcheo by installing required packages
# (Docker, cloudflared), enabling Docker, installing cloudflared as a service,
# running Orcheo setup for a local stack, and configuring Bash history/search ergonomics.
# Requirement: Set CLOUDFLARED_TOKEN in the environment before running.

set -euo pipefail

# Validate prerequisites early before installing anything.
: "${CLOUDFLARED_TOKEN:?CLOUDFLARED_TOKEN is required — set it before running this script.}"

readonly BASHRC="${HOME}/.bashrc"
readonly CLOUDFLARE_KEYRING="/usr/share/keyrings/cloudflare-public-v2.gpg"
readonly CLOUDFLARE_REPO="/etc/apt/sources.list.d/cloudflared.list"

install_dependencies() {
  sudo apt update
  sudo apt install -y docker.io docker-compose-v2

  # Enable and start the docker service
  sudo systemctl enable --now docker

  # Allow current user to run docker commands without sudo after re-login.
  if ! id -nG "$USER" | grep -qw docker; then
    sudo usermod -aG docker "$USER"
  fi
}

install_cloudflared() {
  # Add cloudflare gpg key
  sudo mkdir -p --mode=0755 /usr/share/keyrings
  curl -fsSL https://pkg.cloudflare.com/cloudflare-public-v2.gpg | sudo tee "$CLOUDFLARE_KEYRING" >/dev/null

  # Add cloudflared apt repository
  echo "deb [signed-by=${CLOUDFLARE_KEYRING}] https://pkg.cloudflare.com/cloudflared any main" | sudo tee "$CLOUDFLARE_REPO" >/dev/null

  # Refresh package metadata after adding the repository, then install cloudflared
  sudo apt update
  sudo apt install -y cloudflared

  # Install cloudflared as a service
  sudo cloudflared service install "$CLOUDFLARED_TOKEN"
}

upsert_bashrc_setting() {
  local key="$1"
  local value="$2"

  if grep -Eq "^[[:space:]]*(export[[:space:]]+)?${key}=" "$BASHRC"; then
    sed -i -E "s|^[[:space:]]*(export[[:space:]]+)?${key}=.*$|${key}=${value}|" "$BASHRC"
  else
    echo "${key}=${value}" >> "$BASHRC"
  fi
}

configure_bash_history() {
  touch "$BASHRC"

  upsert_bashrc_setting "HISTSIZE" "10000"
  upsert_bashrc_setting "HISTFILESIZE" "20000"

  # Add key bindings to ~/.bashrc once
  if ! grep -Fq '# >>> orcheo-history-bindings >>>' "$BASHRC"; then
    cat >> "$BASHRC" <<'EOF'

# >>> orcheo-history-bindings >>>
# Enable history search by prefix with Up/Down arrows
bind '"\e[A": history-search-backward'
bind '"\e[B": history-search-forward'

# Also bind Ctrl-P / Ctrl-N (like zsh)
bind '"\C-p": history-search-backward'
bind '"\C-n": history-search-forward'
# <<< orcheo-history-bindings <<<
EOF
  fi
}

install_uv_and_orcheo_sdk() {
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  uv tool install -U orcheo-sdk
}

setup_local_stack() {
  if [[ -n "${ORCHEO_STACK_ASSET_BASE_URL:-}" ]]; then
    export ORCHEO_STACK_ASSET_BASE_URL
  fi
  if id -nG "$USER" | grep -qw docker; then
    sg docker -c "orcheo install --yes --start-local-stack"
    return
  fi
  orcheo install --yes --start-local-stack
}

main() {
  install_dependencies
  install_cloudflared
  install_uv_and_orcheo_sdk
  setup_local_stack
  configure_bash_history
}

main "$@"

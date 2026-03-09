#!/bin/bash
# Replace build-time placeholder strings with runtime environment variable values.
# This runs at container startup via nginx's /docker-entrypoint.d/ mechanism.

HTML_DIR="/usr/share/nginx/html"

# List of VITE_ variables and their placeholder strings
VARS=(
  "VITE_ORCHEO_BACKEND_URL"
  "VITE_ORCHEO_AUTH_ISSUER"
  "VITE_ORCHEO_AUTH_CLIENT_ID"
  "VITE_ORCHEO_AUTH_REDIRECT_URI"
  "VITE_ORCHEO_AUTH_SCOPES"
  "VITE_ORCHEO_AUTH_AUDIENCE"
  "VITE_ORCHEO_AUTH_ORGANIZATION"
  "VITE_ORCHEO_AUTH_PROVIDER_PARAM"
  "VITE_ORCHEO_AUTH_PROVIDER_GOOGLE"
  "VITE_ORCHEO_AUTH_PROVIDER_GITHUB"
  "VITE_ORCHEO_CHATKIT_DOMAIN_KEY"
)

for VAR in "${VARS[@]}"; do
  PLACEHOLDER="__${VAR}__"
  VALUE="${!VAR}"
  if [ -n "$VALUE" ]; then
    echo "canvas-env: injecting $VAR"
    find "$HTML_DIR" -type f \( -name '*.js' -o -name '*.html' \) \
      -exec sed -i "s|${PLACEHOLDER}|${VALUE}|g" {} +
  fi
done

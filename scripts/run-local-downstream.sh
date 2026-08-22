#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
PROJECT_DIR="${SCRIPT_DIR:h}"
INSTANCE_ROOT="${AI2APPS_DOWNSTREAM_BASE_PATH:-/tmp/ai2apps-downstream}"
INSTANCE_PORT="${AI2APPS_DOWNSTREAM_PORT:-8100}"
INSTANCE_KEY="${AI2APPS_DOWNSTREAM_API_KEY:-downstream-local-test-only}"
EMPTY_MODELS="${INSTANCE_ROOT}/empty-models"

mkdir -p "${EMPTY_MODELS}"
export AI2APPS_SECRET_BACKEND="encrypted-file"

exec "${PROJECT_DIR}/.venv/bin/omlx" serve \
  --base-path "${INSTANCE_ROOT}" \
  --model-dir "${EMPTY_MODELS}" \
  --host 127.0.0.1 \
  --port "${INSTANCE_PORT}" \
  --api-key "${INSTANCE_KEY}" \
  --no-hf-cache \
  --no-cache

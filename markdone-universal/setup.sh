#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_PATH="${VAULT_PATH:-${PROJECT_DIR}/../outputs}"

echo "MarkDone setup validation"
echo "Project directory: ${PROJECT_DIR}"
echo "Vault path: ${VAULT_PATH}"

check_command() {
  local command_name="$1"
  if command -v "${command_name}" >/dev/null 2>&1; then
    echo "[ok] ${command_name} found: $(command -v "${command_name}")"
  else
    echo "[error] ${command_name} is not installed or not in PATH"
    return 1
  fi
}

check_command podman
check_command deno

if [[ -d "${VAULT_PATH}" ]]; then
  echo "[ok] Output vault directory exists"
else
  echo "[error] Output vault directory does not exist: ${VAULT_PATH}"
  echo "Create it or set VAULT_PATH to your actual vault directory before deployment."
  exit 1
fi

echo
echo "Setup validation passed."
echo "Next steps:"
echo "  1. chmod +x ./setup.sh ./deploy.sh"
echo "  2. ./deploy.sh"

# Made with Bob

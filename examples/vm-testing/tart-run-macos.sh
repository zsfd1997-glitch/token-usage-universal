#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUT_ROOT="${TOKEN_USAGE_TART_OUTPUT_ROOT:-$SCRIPT_DIR/output/macos-evidence}"
BASE_VM="${TOKEN_USAGE_TART_VM:-}"
RUN_NAME="token-usage-macos-$(date +%Y%m%d-%H%M%S)"
GUEST_REPO_ROOT="${TOKEN_USAGE_TART_GUEST_REPO_ROOT:-$HOME/token-usage-universal}"
GUEST_OUTPUT_DIR="${TOKEN_USAGE_TART_GUEST_OUTPUT_DIR:-/tmp/token-usage-universal-evidence}"

if ! command -v tart >/dev/null 2>&1; then
  echo "tart is required but not installed" >&2
  exit 1
fi

if [ -z "$BASE_VM" ]; then
  echo "Set TOKEN_USAGE_TART_VM to a bootable macOS Tart image" >&2
  exit 1
fi

mkdir -p "$OUTPUT_ROOT"

echo "Cloning Tart VM from $BASE_VM to $RUN_NAME"
tart clone "$BASE_VM" "$RUN_NAME"

cleanup() {
  tart delete "$RUN_NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Starting Tart VM $RUN_NAME"
tart run "$RUN_NAME" >/dev/null 2>&1 &
TART_RUN_PID=$!
sleep 20

echo "Copying repo into guest"
tart copy "$REPO_ROOT" "$RUN_NAME:$GUEST_REPO_ROOT"
echo "Copying collect script into guest"
tart copy "$SCRIPT_DIR/collect-evidence-macos.sh" "$RUN_NAME:$GUEST_REPO_ROOT/examples/vm-testing/collect-evidence-macos.sh"

echo "Running release evidence export inside guest"
tart exec "$RUN_NAME" \
  /bin/bash "$GUEST_REPO_ROOT/examples/vm-testing/collect-evidence-macos.sh" "$GUEST_REPO_ROOT" "$GUEST_OUTPUT_DIR"

echo "Copying evidence bundle back to host"
tart copy "$RUN_NAME:$GUEST_OUTPUT_DIR" "$OUTPUT_ROOT"

kill "$TART_RUN_PID" >/dev/null 2>&1 || true
wait "$TART_RUN_PID" >/dev/null 2>&1 || true

echo "macOS evidence bundle copied to $OUTPUT_ROOT"

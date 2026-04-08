#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${1:-$HOME/token-usage-universal}"
OUTPUT_DIR="${2:-/tmp/token-usage-universal-evidence}"

if [ ! -d "$REPO_ROOT" ]; then
  echo "Repo root not found: $REPO_ROOT" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

cd "$REPO_ROOT"
python3 scripts/token_usage.py release-gate --format json --output-dir "$OUTPUT_DIR"

echo "Evidence bundle exported to $OUTPUT_DIR"

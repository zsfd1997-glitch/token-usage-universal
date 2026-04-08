#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

WORKFLOW_FILE="${TOKEN_USAGE_HOSTLESS_WORKFLOW:-hostless-evidence.yml}"
ARTIFACT_PREFIX="${TOKEN_USAGE_ARTIFACT_PREFIX:-hosted-evidence-$(date +%Y%m%d-%H%M%S)}"
OUTPUT_DIR="${TOKEN_USAGE_HOSTLESS_OUTPUT_DIR:-${SCRIPT_DIR}/output/github-hosted}"
BRANCH_NAME="${TOKEN_USAGE_HOSTLESS_BRANCH:-$(git -C "${REPO_ROOT}" branch --show-current)}"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_command gh
require_command git

cd "${REPO_ROOT}"

if ! gh auth status >/dev/null 2>&1; then
  echo "GitHub CLI is not authenticated. Run: gh auth login" >&2
  exit 1
fi

if ! git ls-remote --exit-code --heads origin "${BRANCH_NAME}" >/dev/null 2>&1; then
  echo "Remote branch origin/${BRANCH_NAME} does not exist." >&2
  echo "Push the branch first so GitHub-hosted runners can see ${WORKFLOW_FILE}." >&2
  exit 1
fi

echo "Dispatching ${WORKFLOW_FILE} on branch ${BRANCH_NAME}..."
gh workflow run "${WORKFLOW_FILE}" \
  --ref "${BRANCH_NAME}" \
  -f "artifact-prefix=${ARTIFACT_PREFIX}"

echo "Waiting for the workflow run to appear..."
RUN_ID=""
for _ in $(seq 1 12); do
  RUN_ID="$(gh run list \
    --workflow "${WORKFLOW_FILE}" \
    --branch "${BRANCH_NAME}" \
    --limit 1 \
    --json databaseId \
    --jq '.[0].databaseId // empty')"
  if [[ -n "${RUN_ID}" ]]; then
    break
  fi
  sleep 5
done

if [[ -z "${RUN_ID}" ]]; then
  echo "Unable to find the dispatched workflow run. Check GitHub Actions manually." >&2
  exit 1
fi

echo "Watching workflow run ${RUN_ID}..."
gh run watch "${RUN_ID}" --interval 10 --exit-status

mkdir -p "${OUTPUT_DIR}"
echo "Downloading artifacts to ${OUTPUT_DIR}..."
gh run download "${RUN_ID}" --dir "${OUTPUT_DIR}"

echo "Done."
echo "Run ID: ${RUN_ID}"
echo "Artifacts: ${OUTPUT_DIR}"

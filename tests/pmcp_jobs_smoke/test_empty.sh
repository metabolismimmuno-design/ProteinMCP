#!/usr/bin/env bash
# Smoke test: empty cache root should produce friendly empty-state message.
set -u
# Resolve project root (two levels up from this file) and put .venv/bin on PATH.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export PATH="$PROJECT_ROOT/.venv/bin:$PATH"

TMP="/tmp/pmcp_jobs_smoke_$$_empty"
mkdir -p "$TMP"
export PMCP_CACHE_ROOT="$TMP"

OUT=$(pmcp jobs 2>&1)
RC=$?
rm -rf "$TMP"

if [ $RC -ne 0 ]; then
    echo "FAIL test_empty: expected exit 0, got $RC" >&2
    echo "$OUT" >&2
    exit 1
fi
if ! echo "$OUT" | grep -q "No jobs found"; then
    echo "FAIL test_empty: expected 'No jobs found' in output" >&2
    echo "$OUT" >&2
    exit 1
fi
echo "PASS test_empty"

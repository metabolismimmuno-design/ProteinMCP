#!/usr/bin/env bash
# Smoke test: 25 valid jobs + --limit 5 -> exactly 5 body rows.
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export PATH="$PROJECT_ROOT/.venv/bin:$PATH"

TMP="/tmp/pmcp_jobs_smoke_$$_limit"
mkdir -p "$TMP/chai1_mcp/jobs"
for i in $(seq -w 1 25); do
    cat > "$TMP/chai1_mcp/jobs/chai1_260411_10${i}_test.json" <<JSON
{
  "job_id": "chai1_260411_10${i}_test",
  "created_at": "2026-04-11T02:${i}:00Z",
  "updated_at": "2026-04-11T02:${i}:30Z",
  "finished_at": "2026-04-11T02:${i}:30Z",
  "status": "completed",
  "run_dir": "/tmp/fixtures/run_${i}"
}
JSON
done
export PMCP_CACHE_ROOT="$TMP"

OUT=$(pmcp jobs --limit 5 2>&1)
RC=$?
rm -rf "$TMP"

if [ $RC -ne 0 ]; then
    echo "FAIL test_limit: expected exit 0, got $RC" >&2
    echo "$OUT" >&2
    exit 1
fi
# Body rows = lines starting with 'chai1_260411_' (deterministic prefix from fixture).
BODY_COUNT=$(echo "$OUT" | grep -c '^chai1_260411_10')
if [ "$BODY_COUNT" -ne 5 ]; then
    echo "FAIL test_limit: expected 5 body rows, got $BODY_COUNT" >&2
    echo "$OUT" >&2
    exit 1
fi

# Also confirm Click rejects --limit 0 with non-zero exit.
OUT2=$(pmcp jobs --limit 0 2>&1)
RC2=$?
if [ $RC2 -eq 0 ]; then
    echo "FAIL test_limit: --limit 0 should be rejected by Click" >&2
    echo "$OUT2" >&2
    exit 1
fi

echo "PASS test_limit"

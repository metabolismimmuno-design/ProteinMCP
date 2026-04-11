#!/usr/bin/env bash
# Smoke test: JSON missing job_id -> row skipped, stderr warning names the field.
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export PATH="$PROJECT_ROOT/.venv/bin:$PATH"

TMP="/tmp/pmcp_jobs_smoke_$$_missing"
mkdir -p "$TMP/chai1_mcp/jobs"
# Missing job_id entirely. Uses 'status' (chai1 disk form) to ensure the
# failure reason is the missing job_id, not the state fallback.
cat > "$TMP/chai1_mcp/jobs/bad.json" <<'JSON'
{
  "created_at": "2026-04-11T02:21:59Z",
  "status": "completed"
}
JSON
export PMCP_CACHE_ROOT="$TMP"

STDOUT=$(pmcp jobs 2>/tmp/pmcp_smoke_$$_err)
RC=$?
STDERR=$(cat /tmp/pmcp_smoke_$$_err)
rm -rf "$TMP" /tmp/pmcp_smoke_$$_err

if [ $RC -ne 0 ]; then
    echo "FAIL test_missing_fields: expected exit 0, got $RC" >&2
    exit 1
fi
if ! echo "$STDERR" | grep -q "missing required field job_id"; then
    echo "FAIL test_missing_fields: expected 'missing required field job_id' on stderr" >&2
    echo "stderr=$STDERR" >&2
    exit 1
fi
if ! echo "$STDOUT" | grep -q "No jobs found"; then
    echo "FAIL test_missing_fields: expected empty-state stdout (all entries invalid)" >&2
    echo "stdout=$STDOUT" >&2
    exit 1
fi
echo "PASS test_missing_fields"

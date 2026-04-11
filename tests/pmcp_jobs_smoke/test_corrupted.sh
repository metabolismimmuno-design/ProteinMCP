#!/usr/bin/env bash
# Smoke test: 1 valid + 1 malformed -> valid row shown, stderr warning, exit 0.
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export PATH="$PROJECT_ROOT/.venv/bin:$PATH"

TMP="/tmp/pmcp_jobs_smoke_$$_corrupted"
mkdir -p "$TMP/chai1_mcp/jobs"
cat > "$TMP/chai1_mcp/jobs/chai1_260411_1021_4149.json" <<'JSON'
{
  "job_id": "chai1_260411_1021_4149",
  "created_at": "2026-04-11T02:21:59Z",
  "updated_at": "2026-04-11T02:23:58Z",
  "finished_at": "2026-04-11T02:23:58Z",
  "status": "completed",
  "run_dir": "/tmp/fixtures/smoke_min"
}
JSON
echo '{not valid json' > "$TMP/chai1_mcp/jobs/chai1_260410_0000_dead.json"
export PMCP_CACHE_ROOT="$TMP"

STDOUT=$(pmcp jobs 2>/tmp/pmcp_smoke_$$_err)
RC=$?
STDERR=$(cat /tmp/pmcp_smoke_$$_err)
rm -rf "$TMP" /tmp/pmcp_smoke_$$_err

if [ $RC -ne 0 ]; then
    echo "FAIL test_corrupted: expected exit 0, got $RC" >&2
    echo "stdout=$STDOUT" >&2
    echo "stderr=$STDERR" >&2
    exit 1
fi
if ! echo "$STDOUT" | grep -q "chai1_260411_1021_4149"; then
    echo "FAIL test_corrupted: expected valid row in stdout" >&2
    echo "$STDOUT" >&2
    exit 1
fi
if ! echo "$STDERR" | grep -q "warning:"; then
    echo "FAIL test_corrupted: expected warning on stderr" >&2
    echo "$STDERR" >&2
    exit 1
fi
if ! echo "$STDERR" | grep -q "chai1_260410_0000_dead.json"; then
    echo "FAIL test_corrupted: warning should name the bad file" >&2
    echo "$STDERR" >&2
    exit 1
fi
echo "PASS test_corrupted"

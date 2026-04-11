#!/usr/bin/env bash
# Smoke test: one chai1-style fixture (uses 'status' + 'output_dir' keys) renders.
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export PATH="$PROJECT_ROOT/.venv/bin:$PATH"

TMP="/tmp/pmcp_jobs_smoke_$$_basic"
mkdir -p "$TMP/chai1_mcp/jobs"
cat > "$TMP/chai1_mcp/jobs/chai1_260411_1021_4149.json" <<'JSON'
{
  "job_id": "chai1_260411_1021_4149",
  "created_at": "2026-04-11T02:21:59Z",
  "updated_at": "2026-04-11T02:23:58Z",
  "finished_at": "2026-04-11T02:23:58Z",
  "status": "completed",
  "modal_call_id": "fc-01KNX5H5KV7MF4ZGYSWSMD9F2F",
  "output_dir": "/tmp/fixtures/smoke_min",
  "run_dir": "/tmp/fixtures/smoke_min",
  "run_name": "smoke_min"
}
JSON
export PMCP_CACHE_ROOT="$TMP"

OUT=$(pmcp jobs 2>&1)
RC=$?
rm -rf "$TMP"

if [ $RC -ne 0 ]; then
    echo "FAIL test_basic: expected exit 0, got $RC" >&2
    echo "$OUT" >&2
    exit 1
fi
for expect in "chai1_260411_1021_4149" "chai1_mcp" "completed"; do
    if ! echo "$OUT" | grep -q "$expect"; then
        echo "FAIL test_basic: expected '$expect' in output" >&2
        echo "$OUT" >&2
        exit 1
    fi
done
echo "PASS test_basic"

# `pmcp jobs` Observability Lite Implementation Plan

> **Status:** ✅ **completed 2026-04-11** — Task 1-6 shipped across commits `effa376` / `d8bb9d7` / `a20ef74` / `c935f6f` / `a79a61a` / `e57fe47`; Task 7 (harness memory sync) closed in the same-day follow-up conversation. Archived under `plans/.archive/` so future triage does not mistake it for pending work. The "ROI #2" label in this plan refers to an **older** review batch and does **not** match the current `project_harness_buildout.md` roadmap.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a read-only `pmcp jobs` subcommand that aggregates per-MCP job caches (`~/.cache/<mcp_name>/jobs/*.json`) into a single ASCII table, replacing the current manual `ls + cat + jq` recipe.

**Architecture:** One new stdlib-only module `src/mcp/jobs_view.py` with three pure-ish functions (`discover_job_files`, `load_job_entries`, `render_table`) plus a `JobEntry` dataclass. A thin Click wrapper in `src/mcp_cli.py` resolves the cache root (env var `PMCP_CACHE_ROOT` → `~/.cache`) and composes the three functions. No touching any tool-mcp, no new dependencies, no changes to `status_cache.py` / `mcps.yaml` / `setup.py` / `environment.yml`. Compatibility with the current `chai1_mcp` on-disk format is handled via `state`⇄`status` and `run_dir`⇄`output_dir` fallbacks inside `normalize_entry`.

**Tech Stack:** Python 3.10+ stdlib only (`click`, `dataclasses`, `fcntl`, `json`, `pathlib`, `datetime`, `os`, `sys`). Tests are POSIX shell scripts under `workspace/pmcp_jobs_smoke/`.

**Reference spec:** `docs/superpowers/specs/2026-04-11-pmcp-jobs-observability-design.md` (authoritative; this plan implements exactly what's in §1–§10 and §13).

---

## File Structure

| Path | Responsibility | Change |
|------|----------------|--------|
| `src/mcp/jobs_view.py` | `JobEntry` dataclass, `discover_job_files`, `normalize_entry`, `load_job_entries`, `render_table`, formatting helpers (`_relative_time`, `_format_elapsed`, `_truncate_run_dir`, `_parse_iso_utc`) | **Create** |
| `src/mcp_cli.py` | Register `jobs_command` Click subcommand + `_resolve_cache_root()` helper (co-located, mirrors style of `status_command`) | **Modify** (append near line 262, before `def main()`) |
| `workspace/pmcp_jobs_smoke/test_empty.sh` | Smoke test: empty cache root → empty-state message | **Create** |
| `workspace/pmcp_jobs_smoke/test_basic.sh` | Smoke test: 1 chai1-style fixture (`status`/`output_dir`) → row rendered | **Create** |
| `workspace/pmcp_jobs_smoke/test_corrupted.sh` | Smoke test: 1 valid + 1 malformed JSON → valid row, stderr warning, exit 0 | **Create** |
| `workspace/pmcp_jobs_smoke/test_missing_fields.sh` | Smoke test: JSON missing `job_id` → skipped with warning, exit 0 | **Create** |
| `workspace/pmcp_jobs_smoke/test_limit.sh` | Smoke test: 25 jobs, `--limit 5` → exactly 5 body rows | **Create** |
| `workspace/pmcp_jobs_smoke/run_all.sh` | Runs all 5 scripts, prints PASS/FAIL, exits non-zero on any failure | **Create** |

No other files are touched. `jobs_view.py` MUST NOT `import modal`, MUST NOT import any `tool-mcps/*` code, and MUST NOT write any file (spec §3.3).

### Why TDD via shell scripts instead of pytest

ProteinMCP has no pytest suite today (spec §9). Introducing one is out of scope for ROI #2. Each smoke test builds its own fake cache under `/tmp/pmcp_jobs_smoke_$$/` and exports `PMCP_CACHE_ROOT` before invoking `pmcp jobs`, so tests are hermetic and do not touch the user's real `~/.cache/` (spec §9.2). The Click command must read `PMCP_CACHE_ROOT` for this to work (spec §10.1) — that wiring is the very first thing Task 1 builds.

---

## Task 1: Scaffold `jobs_view.py` + Click wiring + empty-state behavior

**Files:**
- Create: `src/mcp/jobs_view.py`
- Modify: `src/mcp_cli.py` (add import and `jobs_command` before `def main()` at line 265)
- Create: `workspace/pmcp_jobs_smoke/test_empty.sh`

**Purpose:** Establish the end-to-end wiring — Click option parsing, `PMCP_CACHE_ROOT` resolution, glob returning empty, empty-state message — before touching any normalization or rendering logic. Test-first: write the empty-state smoke test, watch it fail, ship the skeleton, watch it pass.

- [ ] **Step 1: Write the failing smoke test `test_empty.sh`**

Create `workspace/pmcp_jobs_smoke/test_empty.sh`:

```bash
#!/usr/bin/env bash
# Smoke test: empty cache root should produce friendly empty-state message.
set -u
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
```

Make it executable: `chmod +x workspace/pmcp_jobs_smoke/test_empty.sh`

- [ ] **Step 2: Run test to verify it fails**

Run: `bash workspace/pmcp_jobs_smoke/test_empty.sh`
Expected: non-zero exit; stderr shows `Usage: pmcp [OPTIONS] COMMAND...` or `Error: No such command 'jobs'` because the subcommand doesn't exist yet.

- [ ] **Step 3: Create `src/mcp/jobs_view.py` skeleton**

Create `src/mcp/jobs_view.py`:

```python
"""Read-only aggregation view over per-MCP job caches.

Discovers `~/.cache/<mcp_name>/jobs/*.json`, normalizes each entry into a
`JobEntry`, and renders a fixed-width ASCII table. Pure stdlib; no coupling
to Modal SDK or any tool-mcp's Python code. See
`docs/superpowers/specs/2026-04-11-pmcp-jobs-observability-design.md`.
"""
from __future__ import annotations

import fcntl
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class JobEntry:
    job_id: str
    tool: str
    state: str
    created_at: str
    finished_at: str | None
    updated_at: str | None
    run_dir: str | None
    modal_call_id: str | None


def discover_job_files(cache_root: Path) -> list[Path]:
    """Return sorted list of `<cache_root>/*/jobs/*.json` paths. Missing root → []."""
    if not cache_root.exists():
        return []
    return sorted(cache_root.glob("*/jobs/*.json"))


def load_job_entries(paths: list[Path]) -> list[JobEntry]:
    """Placeholder — filled in Task 2."""
    return []


def render_table(entries: list[JobEntry], limit: int) -> str:
    """Placeholder — filled in Task 3."""
    return ""
```

- [ ] **Step 4: Wire `jobs_command` into `src/mcp_cli.py`**

In `src/mcp_cli.py`, at the top import block (after line 20), add:

```python
import os
from .mcp.jobs_view import discover_job_files, load_job_entries, render_table
```

Then immediately before `def main()` at line 265, insert:

```python
def _resolve_cache_root() -> Path:
    """Return ~/.cache unless PMCP_CACHE_ROOT env var overrides (used by smoke tests)."""
    env = os.environ.get("PMCP_CACHE_ROOT")
    if env:
        return Path(env)
    return Path.home() / ".cache"


@cli.command(name="jobs")
@click.option('--limit', type=click.IntRange(min=1), default=20,
              help='Maximum number of jobs to display (default: 20)')
def jobs_command(limit: int):
    """
    Show recent MCP jobs aggregated across all tool caches.

    Reads ~/.cache/<mcp_name>/jobs/*.json (glob), normalizes each entry,
    and renders a single table sorted by creation time descending. Read-only;
    does not poll Modal or modify any file.

    Examples:

      # Show the 20 most recent jobs:
      pmcp jobs

      # Show only the 5 most recent:
      pmcp jobs --limit 5
    """
    cache_root = _resolve_cache_root()
    paths = discover_job_files(cache_root)
    if not paths:
        click.echo("No jobs found. Run an MCP tool first (e.g., chai1_predict).")
        return
    entries = load_job_entries(paths)
    if not entries:
        click.echo("No jobs found. Run an MCP tool first (e.g., chai1_predict).")
        return
    click.echo(render_table(entries, limit))
```

- [ ] **Step 5: Run test_empty.sh to verify it passes**

Run: `bash workspace/pmcp_jobs_smoke/test_empty.sh`
Expected: `PASS test_empty`

Also run the dry invocation manually to confirm Click help works:
`pmcp jobs --help`
Expected: shows `--limit` option with the help text.

- [ ] **Step 6: Commit**

```bash
git add src/mcp/jobs_view.py src/mcp_cli.py workspace/pmcp_jobs_smoke/test_empty.sh
git commit -m "feat(pmcp): scaffold 'pmcp jobs' subcommand with empty-state handling"
```

---

## Task 2: `load_job_entries` + `normalize_entry` with chai1 compatibility

**Files:**
- Modify: `src/mcp/jobs_view.py`
- Create: `workspace/pmcp_jobs_smoke/test_basic.sh`

**Purpose:** Fill in file reading (with `fcntl.LOCK_SH`), per-file normalization with the `state`⇄`status` and `run_dir`⇄`output_dir` fallbacks from spec §7, and return a list of `JobEntry`. Still no real rendering — `render_table` will be replaced by a placeholder that emits just the `job_id`s, enough to assert on. Task 3 will replace render_table with the real version.

- [ ] **Step 1: Write `test_basic.sh`**

Create `workspace/pmcp_jobs_smoke/test_basic.sh`:

```bash
#!/usr/bin/env bash
# Smoke test: one chai1-style fixture (uses 'status' + 'output_dir' keys) renders.
set -u
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
```

Make it executable: `chmod +x workspace/pmcp_jobs_smoke/test_basic.sh`

- [ ] **Step 2: Run test to verify it fails**

Run: `bash workspace/pmcp_jobs_smoke/test_basic.sh`
Expected: FAIL — the empty-state branch triggers because `load_job_entries` returns `[]` (Task 1 placeholder).

- [ ] **Step 3: Implement `normalize_entry` and real `load_job_entries`**

In `src/mcp/jobs_view.py`, replace the placeholder `load_job_entries` and add `normalize_entry` above it:

```python
def normalize_entry(raw: dict, tool: str) -> JobEntry | None:
    """Map raw JSON dict → JobEntry, or None if required fields missing.

    Compatibility: accepts `status` as fallback for `state` (current chai1_mcp
    disk format) and `output_dir` as fallback for `run_dir` (spec §7).
    """
    job_id = raw.get("job_id")
    state = raw.get("state") or raw.get("status")
    created_at = raw.get("created_at")
    if not (job_id and state and created_at):
        return None
    return JobEntry(
        job_id=job_id,
        tool=tool,
        state=state,
        created_at=created_at,
        finished_at=raw.get("finished_at"),
        updated_at=raw.get("updated_at"),
        run_dir=raw.get("run_dir") or raw.get("output_dir"),
        modal_call_id=raw.get("modal_call_id"),
    )


def load_job_entries(paths: list[Path]) -> list[JobEntry]:
    """Read each path under fcntl shared lock, normalize, skip-and-warn on failure.

    The `tool` field of each JobEntry is derived from the cache dir name
    (`<cache_root>/<tool>/jobs/<job_id>.json`). Warnings go to stderr only;
    stdout remains pipe-safe. Task 4 extends this with JSON/permission
    handling; Task 5 extends it with missing-field reporting.
    """
    entries: list[JobEntry] = []
    for path in paths:
        tool = path.parent.parent.name  # .../<tool>/jobs/<file>.json
        with open(path, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                raw = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        entry = normalize_entry(raw, tool)
        if entry is None:
            continue
        entries.append(entry)
    return entries
```

- [ ] **Step 4: Temporary `render_table` that emits one line per entry**

Replace the placeholder `render_table` in `src/mcp/jobs_view.py` with a minimal version that exists only to make Task 2's assertions pass. Task 3 will replace it with the real fixed-width table.

```python
def render_table(entries: list[JobEntry], limit: int) -> str:
    # Task 3 replaces this with a real fixed-width table. For now emit a
    # simple whitespace-separated line per entry so test_basic can assert
    # on job_id / tool / state presence.
    lines = []
    for e in entries[:limit]:
        lines.append(f"{e.job_id}  {e.tool}  {e.state}")
    return "\n".join(lines)
```

- [ ] **Step 5: Run test_basic.sh and test_empty.sh**

Run:
```
bash workspace/pmcp_jobs_smoke/test_empty.sh
bash workspace/pmcp_jobs_smoke/test_basic.sh
```
Expected: both print `PASS`.

- [ ] **Step 6: Commit**

```bash
git add src/mcp/jobs_view.py workspace/pmcp_jobs_smoke/test_basic.sh
git commit -m "feat(pmcp): load and normalize job JSON with chai1 status/output_dir compat"
```

---

## Task 3: Real `render_table` — sort, formatting, column widths

**Files:**
- Modify: `src/mcp/jobs_view.py`

**Purpose:** Replace the temporary `render_table` with the real fixed-width ASCII table specified in §5. Implement `_parse_iso_utc`, `_relative_time`, `_format_elapsed`, `_truncate_run_dir` as pure helpers. Sort entries by `created_at` descending. No new smoke test — `test_basic.sh` already asserts on the three substrings the real renderer must contain.

- [ ] **Step 1: Implement the datetime and formatting helpers**

In `src/mcp/jobs_view.py`, add these helpers above `render_table`:

```python
_TERMINAL_STATES = {"completed", "failed", "cancelled"}


def _parse_iso_utc(s: str | None) -> datetime | None:
    """Parse 'YYYY-MM-DDTHH:MM:SSZ' as UTC. Return None on failure."""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _relative_time(created: datetime | None, now: datetime) -> str:
    """Spec §5.2. Returns '?' if created is None."""
    if created is None:
        return "?"
    delta = now - created
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    if secs < 30 * 86400:
        return f"{secs // 86400}d ago"
    return created.strftime("%Y-%m-%d")


def _format_elapsed(entry: JobEntry, now: datetime) -> str:
    """Spec §5.3. Empty string if neither duration endpoint available."""
    created = _parse_iso_utc(entry.created_at)
    if created is None:
        return ""
    if entry.state in _TERMINAL_STATES:
        end = _parse_iso_utc(entry.finished_at) or _parse_iso_utc(entry.updated_at)
        if end is None:
            return ""
    else:
        end = now
    secs = int((end - created).total_seconds())
    if secs < 0:
        return ""
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m{secs % 60:02d}s"
    if secs < 86400:
        return f"{secs // 3600}h{(secs % 3600) // 60:02d}m"
    return f"{secs // 86400}d"


def _truncate_run_dir(run_dir: str | None, width: int = 40) -> str:
    """Spec §5.4. None → empty string (NOT the literal 'None')."""
    if run_dir is None:
        return ""
    if len(run_dir) <= width:
        return run_dir
    # Keep last (width - 4) chars, prefix with '.../'
    return ".../" + run_dir[-(width - 4):]
```

- [ ] **Step 2: Replace `render_table` with the real implementation**

Replace the temporary `render_table` body from Task 2 with:

```python
# Column widths from spec §5.1
_COL_WIDTHS = [("JOB_ID", 26), ("TOOL", 10), ("STATE", 9),
               ("CREATED", 9), ("ELAPSED", 7), ("RUN_DIR", 40)]


def render_table(entries: list[JobEntry], limit: int) -> str:
    """Sort by created_at desc, head(limit), render fixed-width ASCII table."""
    # Sort newest first. created_at is an ISO 8601 'Z' string, so lexicographic
    # sort is equivalent to chronological sort (all entries in UTC, fixed width).
    # Entries whose created_at failed to parse still have a string; they sort
    # deterministically even if ordering relative to real timestamps is
    # unspecified.
    ordered = sorted(entries, key=lambda e: e.created_at, reverse=True)[:limit]
    now = datetime.now(timezone.utc)

    header = "  ".join(name.ljust(w) for name, w in _COL_WIDTHS).rstrip()
    sep = "  ".join("-" * w for _, w in _COL_WIDTHS).rstrip()
    lines = [header, sep]
    for e in ordered:
        cells = [
            e.job_id.ljust(26)[:26],
            e.tool.ljust(10)[:10],
            e.state.ljust(9)[:9],
            _relative_time(_parse_iso_utc(e.created_at), now).ljust(9)[:9],
            _format_elapsed(e, now).ljust(7)[:7],
            _truncate_run_dir(e.run_dir, 40).ljust(40)[:40],
        ]
        lines.append("  ".join(cells).rstrip())
    return "\n".join(lines)
```

- [ ] **Step 3: Run test_basic.sh and test_empty.sh**

Run:
```
bash workspace/pmcp_jobs_smoke/test_empty.sh
bash workspace/pmcp_jobs_smoke/test_basic.sh
```
Expected: both print `PASS`. The table produced by test_basic contains `chai1_260411_1021_4149`, `chai1_mcp`, and `completed` in separate columns — all three grep assertions still match.

- [ ] **Step 4: Manual visual check against the real chai1_mcp cache**

Run: `pmcp jobs` (no env override, hits `~/.cache/chai1_mcp/jobs/`)
Expected: at least the `chai1_260411_1021_4149` row from spec Appendix A appears; output resembles the example in spec §2; `ELAPSED` shows `1m59s` (because finished_at − created_at = 119s → `1m59s`); `RUN_DIR` shows the `.../outputs/smoke_min` tail-truncated path. Stdout is pipe-safe: `pmcp jobs | head -3` must still show header+sep+first row without ANSI codes.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/jobs_view.py
git commit -m "feat(pmcp): render fixed-width job table with relative time and elapsed columns"
```

---

## Task 4: Corrupted-file handling (skip-and-warn)

**Files:**
- Modify: `src/mcp/jobs_view.py`
- Create: `workspace/pmcp_jobs_smoke/test_corrupted.sh`

**Purpose:** Honor spec §6 core invariant — "no single corrupted or malformed job file may cause `pmcp jobs` to fail". Today `load_job_entries` raises on `JSONDecodeError` / `PermissionError`. Wrap each file read in a try/except that writes a warning to stderr and continues.

- [ ] **Step 1: Write `test_corrupted.sh`**

Create `workspace/pmcp_jobs_smoke/test_corrupted.sh`:

```bash
#!/usr/bin/env bash
# Smoke test: 1 valid + 1 malformed → valid row shown, stderr warning, exit 0.
set -u
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
```

Make it executable: `chmod +x workspace/pmcp_jobs_smoke/test_corrupted.sh`

- [ ] **Step 2: Run test to verify it fails**

Run: `bash workspace/pmcp_jobs_smoke/test_corrupted.sh`
Expected: FAIL — pmcp jobs exits non-zero because `json.load` raises `JSONDecodeError` uncaught.

- [ ] **Step 3: Wrap reads in try/except in `load_job_entries`**

In `src/mcp/jobs_view.py`, replace the body of `load_job_entries` with:

```python
def load_job_entries(paths: list[Path]) -> list[JobEntry]:
    """Read each path under fcntl shared lock, normalize, skip-and-warn on failure.

    Per spec §6, no single corrupted or malformed file may cause the
    command to fail. Warnings go to stderr only.
    """
    entries: list[JobEntry] = []
    for path in paths:
        tool = path.parent.parent.name
        try:
            with open(path, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    raw = json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except json.JSONDecodeError as exc:
            print(f"warning: failed to parse {path} ({type(exc).__name__}); skipping",
                  file=sys.stderr)
            continue
        except PermissionError:
            print(f"warning: {path} permission denied; skipping", file=sys.stderr)
            continue
        except OSError as exc:
            print(f"warning: failed to read {path} ({type(exc).__name__}); skipping",
                  file=sys.stderr)
            continue
        if not isinstance(raw, dict):
            print(f"warning: {path} not a JSON object; skipping", file=sys.stderr)
            continue
        entry = normalize_entry(raw, tool)
        if entry is None:
            # Task 5 adds a specific missing-field warning here.
            continue
        entries.append(entry)
    return entries
```

- [ ] **Step 4: Re-run empty, basic, corrupted**

Run:
```
bash workspace/pmcp_jobs_smoke/test_empty.sh
bash workspace/pmcp_jobs_smoke/test_basic.sh
bash workspace/pmcp_jobs_smoke/test_corrupted.sh
```
Expected: all three print `PASS`.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/jobs_view.py workspace/pmcp_jobs_smoke/test_corrupted.sh
git commit -m "feat(pmcp): skip-and-warn on corrupted/unreadable job cache files"
```

---

## Task 5: Missing-required-field warning (specific field name in message)

**Files:**
- Modify: `src/mcp/jobs_view.py`
- Create: `workspace/pmcp_jobs_smoke/test_missing_fields.sh`

**Purpose:** Spec §6 row 4 — when a required field is absent, the warning must name which field (`"missing required field job_id"`). Today `normalize_entry` returns `None` without telling the caller which field was missing, and `load_job_entries` silently drops the row. Refactor to surface the missing field name.

- [ ] **Step 1: Write `test_missing_fields.sh`**

Create `workspace/pmcp_jobs_smoke/test_missing_fields.sh`:

```bash
#!/usr/bin/env bash
# Smoke test: JSON missing job_id → row skipped, stderr warning names the field.
set -u
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
```

Make it executable: `chmod +x workspace/pmcp_jobs_smoke/test_missing_fields.sh`

- [ ] **Step 2: Run test to verify it fails**

Run: `bash workspace/pmcp_jobs_smoke/test_missing_fields.sh`
Expected: FAIL — normalize_entry returns None but no specific field name reaches stderr.

- [ ] **Step 3: Refactor `normalize_entry` to return `(entry, missing_field)` tuple**

In `src/mcp/jobs_view.py`, replace `normalize_entry`:

```python
def normalize_entry(raw: dict, tool: str) -> tuple[JobEntry | None, str | None]:
    """Map raw → (JobEntry, None) on success, (None, missing_field_name) on failure.

    `state` is satisfied by either `state` or `status` (chai1_mcp disk compat,
    spec §7). `run_dir` likewise falls back to `output_dir`.
    """
    job_id = raw.get("job_id")
    if not job_id:
        return None, "job_id"
    state = raw.get("state") or raw.get("status")
    if not state:
        return None, "state"
    created_at = raw.get("created_at")
    if not created_at:
        return None, "created_at"
    return JobEntry(
        job_id=job_id,
        tool=tool,
        state=state,
        created_at=created_at,
        finished_at=raw.get("finished_at"),
        updated_at=raw.get("updated_at"),
        run_dir=raw.get("run_dir") or raw.get("output_dir"),
        modal_call_id=raw.get("modal_call_id"),
    ), None
```

- [ ] **Step 4: Update `load_job_entries` to log the missing field name**

In `src/mcp/jobs_view.py`, replace the `entry = normalize_entry(raw, tool)` / `if entry is None: continue` block inside `load_job_entries` with:

```python
        entry, missing = normalize_entry(raw, tool)
        if entry is None:
            print(f"warning: {path} missing required field {missing}; skipping",
                  file=sys.stderr)
            continue
        entries.append(entry)
```

- [ ] **Step 5: Re-run all four smoke tests**

Run:
```
bash workspace/pmcp_jobs_smoke/test_empty.sh
bash workspace/pmcp_jobs_smoke/test_basic.sh
bash workspace/pmcp_jobs_smoke/test_corrupted.sh
bash workspace/pmcp_jobs_smoke/test_missing_fields.sh
```
Expected: all four print `PASS`. test_basic still passes because its fixture has all three required fields.

- [ ] **Step 6: Commit**

```bash
git add src/mcp/jobs_view.py workspace/pmcp_jobs_smoke/test_missing_fields.sh
git commit -m "feat(pmcp): warn with specific missing-field name when normalizing jobs"
```

---

## Task 6: `--limit` behavior under load + `run_all.sh` + final integration check

**Files:**
- Create: `workspace/pmcp_jobs_smoke/test_limit.sh`
- Create: `workspace/pmcp_jobs_smoke/run_all.sh`

**Purpose:** Verify `--limit` truncates the body rows (not the header/separator) and that `IntRange(min=1)` already guards `--limit <= 0` from Click itself (no code change needed). Add a `run_all.sh` master runner that execs all five tests with pass/fail summary. Finally do one real-world dry run against `~/.cache/chai1_mcp/`.

- [ ] **Step 1: Write `test_limit.sh`**

Create `workspace/pmcp_jobs_smoke/test_limit.sh`:

```bash
#!/usr/bin/env bash
# Smoke test: 25 valid jobs + --limit 5 → exactly 5 body rows.
set -u
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

# Also confirm Click rejects --limit 0 with exit code 2.
OUT2=$(pmcp jobs --limit 0 2>&1)
RC2=$?
if [ $RC2 -eq 0 ]; then
    echo "FAIL test_limit: --limit 0 should be rejected by Click" >&2
    echo "$OUT2" >&2
    exit 1
fi

echo "PASS test_limit"
```

Make it executable: `chmod +x workspace/pmcp_jobs_smoke/test_limit.sh`

- [ ] **Step 2: Run test_limit.sh to verify it passes**

Run: `bash workspace/pmcp_jobs_smoke/test_limit.sh`
Expected: `PASS test_limit`. If the body row count is not 5, check that `render_table` applies `[:limit]` after sorting (it does in Task 3 step 2). If `--limit 0` is accepted, check the Click decorator uses `type=click.IntRange(min=1)` (it does in Task 1 step 4).

- [ ] **Step 3: Write `run_all.sh`**

Create `workspace/pmcp_jobs_smoke/run_all.sh`:

```bash
#!/usr/bin/env bash
# Run every pmcp jobs smoke test. Exit non-zero if any test fails.
set -u
cd "$(dirname "$0")"

TESTS=(test_empty.sh test_basic.sh test_corrupted.sh test_missing_fields.sh test_limit.sh)
FAILED=0
for t in "${TESTS[@]}"; do
    if bash "$t"; then
        :
    else
        FAILED=$((FAILED + 1))
    fi
done

echo
if [ $FAILED -eq 0 ]; then
    echo "All ${#TESTS[@]} pmcp jobs smoke tests passed."
    exit 0
else
    echo "$FAILED of ${#TESTS[@]} pmcp jobs smoke tests FAILED."
    exit 1
fi
```

Make it executable: `chmod +x workspace/pmcp_jobs_smoke/run_all.sh`

- [ ] **Step 4: Run the master suite**

Run: `bash workspace/pmcp_jobs_smoke/run_all.sh`
Expected: five `PASS ...` lines, then `All 5 pmcp jobs smoke tests passed.`, exit 0.

- [ ] **Step 5: Real-world integration check against the live chai1_mcp cache**

Run: `pmcp jobs` (no env override, hits `~/.cache/chai1_mcp/jobs/`)
Expected:
- The row for `chai1_260411_1021_4149` (from spec Appendix A) is present
- `TOOL` column shows `chai1_mcp`
- `STATE` column shows `completed`
- `ELAPSED` column shows `1m59s` (finished_at − created_at = 119s)
- `RUN_DIR` column shows a tail-truncated path ending in `outputs/smoke_min`
- Stdout has no ANSI color codes: `pmcp jobs | cat` produces identical output to `pmcp jobs`
- `pmcp jobs | head -3` shows header + separator + first row

If the output looks wrong, rerun `bash workspace/pmcp_jobs_smoke/run_all.sh` to confirm the formatters are still green — a real-cache surprise may point to a field the fixtures didn't exercise, which is itself actionable (file a note and iterate).

- [ ] **Step 6: Commit**

```bash
git add workspace/pmcp_jobs_smoke/test_limit.sh workspace/pmcp_jobs_smoke/run_all.sh
git commit -m "test(pmcp): add limit/run_all smoke tests for 'pmcp jobs' command"
```

---

## Task 7: Harness wrap-up (memory + spec cross-link)

**Files:**
- Modify: `~/.claude/memory/project_harness_buildout.md`
- Modify: `~/.claude/memory/MEMORY.md`

**Purpose:** Close the ROI #2 loop in the user's personal harness memory so the next session knows this item is done and what the next candidate is. Follows the "对话结束" checklist from `~/.claude/CLAUDE.md` and harness principle 5 (conversation split = state boundary). No changes to project source tree in this task — it's pure book-keeping.

- [ ] **Step 1: Append a "Done (YYYY-MM-DD) ROI #2" block to `project_harness_buildout.md`**

In `~/.claude/memory/project_harness_buildout.md`, add a new dated section under the existing "已完成" blocks that summarizes:
- What shipped: `pmcp jobs` subcommand + `src/mcp/jobs_view.py` + 5 smoke tests
- Key design decisions locked in (schema v1 contract, `state`/`status` compat, read-only v0)
- What's deferred to v1 (spec §12 items, esp. `--refresh` requiring ≥2 MCP consumers)
- Which harness principles this strengthened (1, 3, 6)
- Bump `last_verified: 2026-04-11` if not already current

Also update the "下一步候选 ROI" list: remove the **ROI #2** bullet, and promote either "chai1_mcp remote 推送" or "下一个高频 MCP 化候选 (频率快照刷新)" to the top of the list as the new default.

- [ ] **Step 2: Update the `MEMORY.md` index line**

In `~/.claude/memory/MEMORY.md`, update the first bullet (the `project_harness_buildout.md` pointer) to reflect that ROI #2 is done. Replace the tail "下一对话首选 ROI #2 可观测性 lite (`pmcp jobs`)" with whatever the new top candidate is (chai1_mcp remote push, or frequency refresh, or whichever the user chose in Step 1).

- [ ] **Step 3: Commit the ProteinMCP side**

The harness memory changes live in `~/.claude/`, which is not a git repo (see `project_harness_buildout.md` note). No commit needed there. In the ProteinMCP repo, all tasks 1-6 have already been committed; `git status` should be clean (except for any in-progress items unrelated to this plan). Verify with:

```bash
cd /Users/guoxingchen/claude-project/ProteinMCP && git status
git log --oneline -8
```

Expected: the 6 commits from tasks 1-6 are visible on `main`, working tree clean.

- [ ] **Step 4: Prompt the user to open a new conversation**

Per `~/.claude/CLAUDE.md` → 工作节奏 → 对话结束 → 步骤 4, print a short message telling the user that ROI #2 is done and the next conversation should pick up whichever candidate they promoted in Step 1.

---

## Self-Review Notes (author check against spec)

- §1 motivation / §2 interface / §3 architecture → Task 1 (scaffold + CLI wiring + `_resolve_cache_root`)
- §4 data flow + §4.1 `JobEntry` → Tasks 1 and 2
- §4.2 required/optional fields → Task 2 (normalize_entry) + Task 5 (specific missing-field reporting)
- §5 rendering (column widths, relative time, elapsed, run_dir truncation, no color) → Task 3
- §6 error handling table:
  - "cache does not exist" / "no matches" → Task 1 (`discover_job_files` returns `[]`)
  - "JSON parse error" / "permission denied" → Task 4
  - "missing required field" → Task 5
  - "LOCK_SH blocks until released" → Task 2 (implicit; `fcntl.flock(LOCK_SH)` is blocking by default)
  - "`created_at` unparseable shows `?`, row NOT skipped" → Task 3 (`_relative_time` returns `?` on None; `_format_elapsed` returns empty string; neither triggers skip)
  - "`--limit <= 0` → exit 2" → Task 1 (`click.IntRange(min=1)`) + Task 6 verifies
  - "all files corrupted → empty-state" → Task 1's "`if not entries:` fall-through" branch
- §7 normalization rules (state⇄status, run_dir⇄output_dir) → Task 2 initial, Task 5 refactor to tuple return
- §8 schema v1 contract → documented in spec only; `normalize_entry` is the enforcement surface
- §9 testing → Tasks 1, 2, 4, 5, 6 each ship one smoke test; Task 6 adds `run_all.sh`
- §10.1 `PMCP_CACHE_ROOT` → Task 1 step 4
- §10.2 fcntl availability → existing project assumption, no new code
- §10.3 datetime parsing (no `utcnow`) → Task 3 step 1
- §10.4 Click help text style → Task 1 step 4 matches `status_command`
- §11 harness alignment → Task 7 records it in memory
- §12 deferred work → explicitly not implemented; cross-referenced in Task 7
- §13 open questions → none; all 4 resolved in spec

No placeholders remain. All required fields and type names (`JobEntry`, `state`/`status`/`run_dir`/`output_dir`, `PMCP_CACHE_ROOT`) are consistent across tasks. Method signatures:
- `discover_job_files(cache_root: Path) -> list[Path]` — consistent in Tasks 1–6
- `normalize_entry(raw, tool) -> tuple[JobEntry | None, str | None]` after Task 5 refactor; Task 2's single-return version is explicitly replaced in Task 5 step 3
- `load_job_entries(paths) -> list[JobEntry]` — public signature unchanged across tasks; body grows
- `render_table(entries, limit) -> str` — public signature unchanged; Task 3 replaces body

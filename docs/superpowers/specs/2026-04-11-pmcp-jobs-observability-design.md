# Spec: `pmcp jobs` — Observability Lite (v0)

**Date**: 2026-04-11
**Status**: ✅ **Implemented 2026-04-11** (plan archived at `docs/superpowers/plans/.archive/2026-04-11-pmcp-jobs-observability.md`). This doc is retained as reference for the design decisions that are now frozen in `src/mcp/jobs_view.py`. The "ROI #2" label below refers to an **older** review batch and does not match the current `project_harness_buildout.md` roadmap.
**Scope**: ROI #2 of personal harness buildout (see `~/.claude/memory/project_harness_buildout.md`)
**Supersedes**: N/A (first spec in ProteinMCP repo)

---

## 1. Motivation

Today, to answer "what MCP jobs are running / have I run recently?", a user must manually:

```bash
ls ~/.cache/chai1_mcp/jobs/
cat ~/.cache/chai1_mcp/jobs/chai1_260411_1021_4149.json | jq .
```

This scales poorly: as more MCPs adopt the `~/.cache/<mcp_name>/jobs/*.json` convention (currently only `chai1_mcp` does), the user needs one command that aggregates across all of them.

`pmcp jobs` is that command. v0 is **read-only**: it globs the cache directories, parses each job file, and renders a single table.

### Non-goals for v0

- Live Modal status polling (no `--refresh`) — deferred to v1, needs a second MCP with job cache before the abstraction is worth extracting.
- Filtering by state / tool — YAGNI at 1 MCP.
- Colored output, JSON output, watch mode.
- Modifying any existing MCP (chai1_mcp is NOT touched — compatibility via field fallback).

### Why read-only first (harness principle 6)

Zero-cost high-value first. `pmcp jobs` v0 is pure stdlib, ~150 LOC, zero new dependencies, zero coupling to `modal` SDK or any MCP's Python code. Every day it saves you `ls + cat + jq`. A `--refresh` mode is worth building only when the "live Modal poll" logic has ≥2 consumers to validate the abstraction.

---

## 2. Command Interface

```
$ pmcp jobs [--limit N]

Options:
  --limit INTEGER RANGE  Maximum number of jobs to display [default: 20; x>=1]
  --help                 Show this message and exit.
```

No other flags in v0. Future flags (`--refresh`, `--state`, `--tool`, `--wide`, `--json`) are explicitly deferred.

### Example output

```
$ pmcp jobs
JOB_ID                      TOOL        STATE      CREATED    ELAPSED  RUN_DIR
--------------------------  ----------  ---------  ---------  -------  ----------------------------------------
chai1_260411_1021_4149      chai1_mcp   completed  2h ago     1m59s    .../chai1_mcp_smoke_test/outputs/smoke_min
chai1_260410_1832_a3b1      chai1_mcp   running    18h ago    18h12m   .../hsv1_nanobody/chai1_validation/r03
chai1_260409_0942_7c55      chai1_mcp   failed     2d ago     3m14s    .../hsv1_nanobody/chai1_validation/r01
```

### Empty state

```
$ pmcp jobs
No jobs found. Run an MCP tool first (e.g., chai1_predict).
```

Exit code `0`. (Rationale: empty is not an error, it's a valid "nothing to show" state.)

---

## 3. Architecture

### 3.1 Files changed / added

| File | Change | Rough LOC |
|------|--------|-----------|
| `src/mcp/jobs_view.py` | **New** — core logic | ~150 |
| `src/mcp_cli.py` | **Modified** — register `jobs_command` subcommand | ~15 |
| `workspace/pmcp_jobs_smoke/test_*.sh` | **New** — 5 smoke test scripts | ~100 total |
| `docs/superpowers/specs/2026-04-11-pmcp-jobs-observability-design.md` | **New** — this spec | — |

No changes to: `setup.py`, `environment.yml`, `mcps.yaml`, any tool-mcp, `status_cache.py`.

### 3.2 Component boundaries

`jobs_view.py` exposes three functions, each with one purpose and testable in isolation:

```python
def discover_job_files(cache_root: Path | None = None) -> list[Path]:
    """Glob ~/.cache/*/jobs/*.json. cache_root defaults to ~/.cache; override for tests."""

def load_job_entries(paths: list[Path]) -> list[JobEntry]:
    """Read each file under fcntl shared lock, normalize fields, skip-and-warn on failure."""

def render_table(entries: list[JobEntry], limit: int) -> str:
    """Sort by created_at desc, head(limit), render fixed-width ASCII table. Pure function."""
```

The Click command is a thin wrapper (see §10.1 for `_resolve_cache_root` which respects `PMCP_CACHE_ROOT`):

```python
def jobs_command(limit: int) -> None:
    cache_root = _resolve_cache_root()
    paths = discover_job_files(cache_root)
    if not paths:
        click.echo("No jobs found. Run an MCP tool first (e.g., chai1_predict).")
        return
    entries = load_job_entries(paths)
    if not entries:  # all files corrupted
        click.echo("No jobs found. Run an MCP tool first (e.g., chai1_predict).")
        return
    click.echo(render_table(entries, limit))
```

### 3.3 What `jobs_view.py` must NOT do

- `import modal` — no runtime coupling to Modal SDK
- `import chai1_mcp.*` — no coupling to any tool-mcp Python code
- Subprocess `claude mcp call ...` — deferred to v1 `--refresh`
- Write any file — pure read-only
- Touch `src/mcp/status_cache.py` — different concern (MCP install state, not job state)

---

## 4. Data Flow

```
~/.cache/*/jobs/*.json  ──(glob)──▶  list[Path]
                                        │
                                        ▼
                                  open + fcntl.LOCK_SH
                                        │
                                        ▼
                                   raw dict per job
                                        │
                                        ▼
                           normalize_entry(raw, cache_dir_name)
                                        │
                                        ▼
                                   JobEntry (dataclass)
                                        │
                                        ▼
                            sort by created_at desc, head(N)
                                        │
                                        ▼
                                   render_table() ──▶ stdout
```

### 4.1 JobEntry dataclass (internal to `jobs_view.py`)

```python
from dataclasses import dataclass

@dataclass
class JobEntry:
    job_id: str
    tool: str                 # derived from cache dir name (e.g., "chai1_mcp")
    state: str                # normalized: raw.get("state") or raw.get("status") or "unknown"
    created_at: str           # raw ISO string; used as sort key directly
    finished_at: str | None
    updated_at: str | None
    run_dir: str | None       # raw.get("run_dir") or raw.get("output_dir") or None
    modal_call_id: str | None
```

### 4.2 Required vs optional fields when parsing

**Required** (missing → skip with stderr warning):
- `job_id`
- `state` or `status` (at least one must be present)
- `created_at`

**Optional** (missing → `None` or empty):
- everything else

---

## 5. Rendering Details

### 5.1 Column widths (fixed, chars)

| Column | Width | Notes |
|--------|------:|-------|
| `JOB_ID` | 26 | long enough for `chai1_260411_1021_4149` (22 chars) + slack |
| `TOOL` | 10 | fits `chai1_mcp`, `boltz_mcp`, `bindcraft_mcp` truncates to `bindcraft_` |
| `STATE` | 9 | fits `completed`, `cancelled` |
| `CREATED` | 9 | relative time, e.g. `2h ago`, `2026-04-11` if >30d |
| `ELAPSED` | 7 | e.g. `1m59s`, `18h12m`, `3d` |
| `RUN_DIR` | 40 | tail-truncated with `...` prefix |

Total width: ~105 chars. No terminal auto-adapt in v0.

### 5.2 Relative time format (`CREATED` column)

Given `delta = now - created_at`:

| Range | Format | Example |
|-------|--------|---------|
| `< 60s` | `Ns ago` | `42s ago` |
| `< 60m` | `Nm ago` | `17m ago` |
| `< 24h` | `Nh ago` | `2h ago` |
| `< 30d` | `Nd ago` | `5d ago` |
| `≥ 30d` | `YYYY-MM-DD` | `2026-03-10` |

### 5.3 Elapsed format (`ELAPSED` column)

**Duration source**:
- `state in {pending, running}` → `now - created_at`
- `state in {completed, failed, cancelled}` → `finished_at - created_at` (fallback: `updated_at - created_at`; if both missing → empty string)

**Format**:
- `< 60s` → `Ns` (e.g., `42s`)
- `< 60m` → `NmSSs` (e.g., `1m59s`)
- `< 24h` → `NhMMm` (e.g., `18h12m`)
- `≥ 24h` → `Nd` (integer days, e.g., `3d`)

### 5.4 `RUN_DIR` truncation

- `len(run_dir) ≤ 40` → display as-is
- `len(run_dir) > 40` → `".../" + run_dir[-37:]`
- `run_dir is None` → empty string (NOT the literal `"None"`)

### 5.5 No color

v0 prints plain ASCII. Rationale: `pmcp jobs | grep running` must work transparently; ANSI escape codes complicate isatty detection and pipe handling. Color can be added in v1 if desired.

---

## 6. Error Handling

Core invariant: **no single corrupted or malformed job file may cause `pmcp jobs` to fail**. At least one valid entry → valid table output. Zero valid entries → empty-state message.

| Condition | Behavior | Exit |
|-----------|----------|-----:|
| `~/.cache/` does not exist | empty-state message on stdout | 0 |
| `~/.cache/` exists, no `*/jobs/*.json` matches | empty-state message | 0 |
| JSON parse error on a file | stderr: `warning: failed to parse <path> (JSONDecodeError); skipping`; continue | 0 |
| File missing required field (`job_id` / `state`+`status` / `created_at`) | stderr: `warning: <path> missing required field <X>; skipping`; continue | 0 |
| File held by another process's exclusive lock | `fcntl.LOCK_SH` blocks until released (same as `chai1_mcp.JobStore.load`); no timeout in v0 | 0 |
| `created_at` unparseable | `CREATED` column shows `?`; row NOT skipped | 0 |
| Permission denied on a file | stderr: `warning: <path> permission denied; skipping` | 0 |
| `--limit <= 0` | click `IntRange(min=1)` rejects at parse time | 2 |
| All files corrupted → `entries` empty | empty-state message (same as no-files case) | 0 |

Warnings go to **stderr only**, stdout stays clean and pipe-safe.

---

## 7. Normalization Rules (raw JSON → JobEntry)

```python
def normalize_entry(raw: dict, tool: str) -> JobEntry | None:
    # Required fields
    job_id = raw.get("job_id")
    state = raw.get("state") or raw.get("status")  # chai1_mcp uses "status" on disk
    created_at = raw.get("created_at")
    if not (job_id and state and created_at):
        return None  # caller logs warning with specific missing field

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
```

**Why `state` fallback to `status`**: the current `chai1_mcp` persists the field as `status` in `~/.cache/chai1_mcp/jobs/*.json` (see `tool-mcps/chai1_mcp/src/server.py:374`), while its MCP API response uses `state`. To avoid touching chai1_mcp at all, `jobs_view.py` accepts either on disk. New MCPs following this spec should use `state`.

**Why `run_dir` fallback to `output_dir`**: same compatibility reason.

---

## 8. Job JSON Schema v1 (contract for future MCPs)

This section is the **public contract** for any MCP that wants to show up in `pmcp jobs`. MCPs that follow it get aggregation for free; MCPs that don't simply don't appear in the table (they can still work fine on their own).

### 8.1 Required file location

`~/.cache/<mcp_name>/jobs/<job_id>.json`

- `<mcp_name>` SHOULD match the MCP's registered name in `src/mcp/configs/mcps.yaml`
- `<job_id>` SHOULD be globally unique; recommended format: `<tool_prefix>_<YYMMDD_HHMM>_<4hex>`

### 8.2 Required fields

```json
{
  "job_id": "chai1_260411_1021_4149",
  "state": "completed",
  "created_at": "2026-04-11T02:21:59Z",
  "updated_at": "2026-04-11T02:23:58Z"
}
```

- `job_id`: string, matches filename stem
- `state`: enum, one of `pending` | `running` | `completed` | `failed` | `cancelled`
- `created_at`: ISO 8601 UTC, format `%Y-%m-%dT%H:%M:%SZ`
- `updated_at`: ISO 8601 UTC, same format, updated on every state change

### 8.3 Recommended optional fields

- `finished_at`: ISO 8601 UTC, set when state transitions to `completed` / `failed` / `cancelled`
- `modal_call_id`: string, if the MCP uses Modal — enables future `--refresh` v1
- `run_dir`: absolute path to the output directory (preferred over `output_dir`)
- `warnings`: list of strings, default `[]`

### 8.4 Tool-specific fields

Any other fields (`run_name`, `n_output_files`, `input_faa_name`, `params`, `log_path`, …) are **tool-specific** and will be **silently ignored** by `pmcp jobs`. MCPs are free to add whatever they need for their own bookkeeping.

### 8.5 Concurrency

Writers MUST use `fcntl.LOCK_EX` when writing; readers SHOULD use `fcntl.LOCK_SH`. `chai1_mcp.JobStore` is the reference implementation (`tool-mcps/chai1_mcp/src/utils.py:241-290`).

### 8.6 Backward compatibility

- `state` ⇄ `status`: `pmcp jobs` accepts either as a one-time compatibility gesture for the current `chai1_mcp` disk format. **New MCPs MUST use `state`**.
- `run_dir` ⇄ `output_dir`: same compatibility gesture; new MCPs SHOULD use `run_dir`.

These compatibility aliases are noted here so they can be removed in a future schema v2 without confusion.

---

## 9. Testing

ProteinMCP has no pytest suite today; introducing one is out of scope for ROI #2. Instead, smoke tests as shell scripts in `workspace/pmcp_jobs_smoke/`:

### 9.1 Test cases

| Script | Scenario | Assertion |
|--------|----------|-----------|
| `test_empty.sh` | Point `HOME` at empty temp dir | stdout contains `"No jobs found"`, exit 0 |
| `test_basic.sh` | Write a fixture job JSON (chai1-style, `status=completed`) into a temp cache root | stdout contains the fixture's `job_id`, tool name, `completed`; exit 0 |
| `test_corrupted.sh` | Fake cache: 1 valid + 1 `{not valid json` | stdout has valid row, stderr has warning, exit 0 |
| `test_missing_fields.sh` | Fake cache: 1 JSON missing `job_id` | stderr has "missing required field job_id" warning, skipped in table, exit 0 |
| `test_limit.sh` | Fake cache with 25 valid jobs, run `pmcp jobs --limit 5` | table body has exactly 5 data rows |

### 9.2 Isolation

All 5 tests build their own fake cache under `/tmp/pmcp_jobs_smoke_<pid>/<mcp_name>/jobs/` and export `PMCP_CACHE_ROOT=/tmp/pmcp_jobs_smoke_<pid>` before invoking `pmcp jobs`. This keeps tests hermetic — they don't touch or depend on the user's real `~/.cache/`. The `PMCP_CACHE_ROOT` override is implemented per §10.1.

### 9.3 Run script

`workspace/pmcp_jobs_smoke/run_all.sh` runs all 5 tests, prints PASS/FAIL per test, exits non-zero if any fail.

---

## 10. Implementation Notes

### 10.1 Handling `cache_root` in the Click command

The Click command `jobs_command` should respect env var `PMCP_CACHE_ROOT` (if set) before falling back to `~/.cache`. This enables shell-level smoke tests without monkeypatching.

```python
def _resolve_cache_root() -> Path:
    env = os.environ.get("PMCP_CACHE_ROOT")
    if env:
        return Path(env)
    return Path.home() / ".cache"
```

### 10.2 fcntl availability

`fcntl` is POSIX-only (Linux + macOS). Since ProteinMCP already uses `fcntl` in `src/mcp/status_cache.py` and `chai1_mcp/src/utils.py`, this is an existing project-wide assumption — no new portability burden.

### 10.3 `datetime` parsing

Use `datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)` to parse, and `datetime.now(timezone.utc)` for the current time. Do NOT use `datetime.utcnow()` (deprecated in 3.12; returns naive).

### 10.4 Click help text style

Match existing `pmcp status` help text style (see `src/mcp_cli.py:126-144`).

---

## 11. Harness Alignment

- **Principle 1** (encode into system, not prompt): replaces manual `ls + cat + jq` recipe with a CLI command. ✅
- **Principle 3** (thinner manuals): future `feedback_*.md` entries for "how to check job status" can link to `pmcp jobs` instead of documenting the cache path. ✅
- **Principle 6** (zero-cost high-value first): stdlib only, no new deps, no MCP changes, no hooks. Expected ~150 LOC + tests. ✅
- **Principle 5** (conversation split = harness state boundary): this spec + smoke tests are one conversation's worth of output; the actual implementation should be a separate conversation triggered by `writing-plans`.

---

## 12. Deferred Work (v1+)

Tracked for later, NOT in scope for this spec:

1. **`--refresh` flag**: poll live Modal state for pending/running jobs. Wait for a second MCP with job cache to validate the abstraction (avoid N=1 shaping).
2. **Filtering**: `--state <state>`, `--tool <name>`, `--since <duration>`.
3. **Wide mode**: `--wide` shows `modal_call_id` and more columns.
4. **JSON output**: `--json` for scripting.
5. **Watch mode**: `--watch [INTERVAL]` live refresh.
6. **Cost view**: if Modal publishes per-call cost via FunctionCall API, add a `COST` column in v2.
7. **Cleanup command**: `pmcp jobs prune --older-than 30d` to GC old cache files.
8. **Removing `status` / `output_dir` compatibility aliases**: once chai1_mcp is updated to write `state` / `run_dir` directly, drop the fallbacks from `normalize_entry` (schema v2).

---

## 13. Open Questions

None at spec close. All four clarifying questions resolved during brainstorming:

1. Scope → option A (read-only viewer)
2. Columns → `JOB_ID`, `TOOL`, `STATE`, `CREATED`, `ELAPSED`, `RUN_DIR`
3. Filters → `--limit N` only
4. Error handling → skip-and-warn on stderr, friendly empty-state message

---

## Appendix A: Sample `chai1_mcp` job JSON (real)

From `~/.cache/chai1_mcp/jobs/chai1_260411_1021_4149.json`:

```json
{
    "job_id": "chai1_260411_1021_4149",
    "created_at": "2026-04-11T02:21:59Z",
    "updated_at": "2026-04-11T02:23:58Z",
    "status": "completed",
    "modal_call_id": "fc-01KNX5H5KV7MF4ZGYSWSMD9F2F",
    "input_faa_source": "/Users/guoxingchen/biomodals/test_chai1.faa",
    "input_faa_name": "test_chai1.faa",
    "output_dir": "/Users/guoxingchen/claude-project/ProteinMCP/workspace/chai1_mcp_smoke_test/outputs",
    "run_name": "smoke_min",
    "run_dir": "/Users/guoxingchen/claude-project/ProteinMCP/workspace/chai1_mcp_smoke_test/outputs/smoke_min",
    "params": { "num_trunk_recycles": 1, "num_diffn_timesteps": 10, "seed": 42, "use_esm_embeddings": true, "gpu": null, "timeout_min": null, "chai1_kwargs": {} },
    "log_path": "/Users/guoxingchen/.cache/chai1_mcp/logs/chai1_260411_1021_4149.log",
    "warnings": [],
    "finished_at": "2026-04-11T02:23:58Z",
    "n_output_files": 10,
    "_outputs_in_memory": false
}
```

Note: the on-disk field is `status`, not `state`. `normalize_entry` handles this via the `state or status` fallback (§7).

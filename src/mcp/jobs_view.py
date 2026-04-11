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
    """Return sorted list of `<cache_root>/*/jobs/*.json` paths. Missing root -> []."""
    if not cache_root.exists():
        return []
    return sorted(cache_root.glob("*/jobs/*.json"))


def normalize_entry(raw: dict, tool: str) -> JobEntry | None:
    """Map raw JSON dict -> JobEntry, or None if required fields missing.

    Compatibility: accepts `status` as fallback for `state` (current chai1_mcp
    disk format) and `output_dir` as fallback for `run_dir` (spec section 7).
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
    (`<cache_root>/<tool>/jobs/<job_id>.json`). Task 4 extends this with
    JSON/permission handling; Task 5 extends with missing-field reporting.
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


def render_table(entries: list[JobEntry], limit: int) -> str:
    # Task 3 replaces this with a real fixed-width table. For now emit a
    # simple whitespace-separated line per entry so test_basic can assert
    # on job_id / tool / state presence.
    lines = []
    for e in entries[:limit]:
        lines.append(f"{e.job_id}  {e.tool}  {e.state}")
    return "\n".join(lines)

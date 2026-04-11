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


def normalize_entry(raw: dict, tool: str) -> tuple[JobEntry | None, str | None]:
    """Map raw -> (JobEntry, None) on success, (None, missing_field) on failure.

    `state` is satisfied by either `state` or `status` (chai1_mcp disk compat,
    spec section 7). `run_dir` likewise falls back to `output_dir`.
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


def load_job_entries(paths: list[Path]) -> list[JobEntry]:
    """Read each path under fcntl shared lock, normalize, skip-and-warn on failure.

    Per spec section 6, no single corrupted or malformed file may cause the
    command to fail. Warnings go to stderr only; stdout remains pipe-safe.
    """
    entries: list[JobEntry] = []
    for path in paths:
        tool = path.parent.parent.name  # .../<tool>/jobs/<file>.json
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
        entry, missing = normalize_entry(raw, tool)
        if entry is None:
            print(f"warning: {path} missing required field {missing}; skipping",
                  file=sys.stderr)
            continue
        entries.append(entry)
    return entries


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
    """Spec section 5.2. Returns '?' if created is None."""
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
    """Spec section 5.3. Empty string if neither duration endpoint available."""
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
    """Spec section 5.4. None -> empty string (NOT the literal 'None')."""
    if run_dir is None:
        return ""
    if len(run_dir) <= width:
        return run_dir
    # Keep last (width - 4) chars, prefix with '.../'
    return ".../" + run_dir[-(width - 4):]


# Column widths from spec section 5.1
_COL_WIDTHS = [("JOB_ID", 26), ("TOOL", 10), ("STATE", 9),
               ("CREATED", 9), ("ELAPSED", 7), ("RUN_DIR", 40)]


def render_table(entries: list[JobEntry], limit: int) -> str:
    """Sort by created_at desc, head(limit), render fixed-width ASCII table."""
    # Sort newest first. created_at is an ISO 8601 'Z' string, so lexicographic
    # sort is equivalent to chronological sort (all entries in UTC, fixed width).
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

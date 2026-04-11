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


def load_job_entries(paths: list[Path]) -> list[JobEntry]:
    """Placeholder -- filled in Task 2."""
    return []


def render_table(entries: list[JobEntry], limit: int) -> str:
    """Placeholder -- filled in Task 3."""
    return ""

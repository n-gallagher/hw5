"""Append-only audit trail: output/audit_trail.json.

Every step of every agent loop adds one record: who (run, ticket, agent,
hand-off chain), what (the model's tool calls and text, the tool results),
why (the model's reasoning summary when it gives one), and what it cost
(tokens per step). The file is a JSON list that only ever grows: each write
reads the list, adds records and atomically replaces the file. It is never
wiped. Secrets are never logged.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any

from backend.config import AUDIT_TRAIL

_MAX = 2000  # cap long strings so one step can't bloat the file
_lock = threading.RLock()
_KEY_RE = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|pk-[A-Za-z0-9_\-]{8,}|Bearer\s+\S+)")


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        value = _KEY_RE.sub("[REDACTED]", value)
        return value if len(value) <= _MAX else value[:_MAX] + f"... [truncated {len(value) - _MAX} chars]"
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _clean(str(value))


# Records that couldn't be written yet (file locked) wait here, one JSON per line,
# and are folded into the trail on the next successful write. Nothing is dropped.
BACKLOG = AUDIT_TRAIL.with_name("audit_trail.backlog.jsonl")


def _retry(fn, attempts: int = 40):
    """Windows refuses to read/replace a file another process (OneDrive sync, a
    reader) has open for a moment. Retry with a short backoff (about 6 s total)."""
    for i in range(attempts):
        try:
            return fn()
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(min(0.05 * (i + 1), 0.3))


def read_all() -> list[dict]:
    """Read the whole trail. Uses the same lock as writers so a reader in this
    process (the dashboard's /api/events) never holds the file during a replace."""
    with _lock:
        if not AUDIT_TRAIL.exists() or not AUDIT_TRAIL.stat().st_size:
            return []
        return json.loads(_retry(lambda: AUDIT_TRAIL.read_text(encoding="utf-8")))


def _write(records: list[dict]) -> None:
    with _lock:
        AUDIT_TRAIL.parent.mkdir(parents=True, exist_ok=True)
        existing: list = []
        if AUDIT_TRAIL.exists() and AUDIT_TRAIL.stat().st_size:
            try:
                existing = json.loads(_retry(lambda: AUDIT_TRAIL.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                # never lose history: keep the unreadable file aside and start a new list
                AUDIT_TRAIL.replace(AUDIT_TRAIL.with_suffix(f".corrupt-{datetime.now():%Y%m%d%H%M%S}.json"))
        backlog: list[dict] = []
        if BACKLOG.exists():
            backlog = [json.loads(line) for line in BACKLOG.read_text(encoding="utf-8").splitlines() if line.strip()]
        existing.extend(backlog + records)
        tmp = AUDIT_TRAIL.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(existing, indent=1, ensure_ascii=False), encoding="utf-8")
        _retry(lambda: os.replace(tmp, AUDIT_TRAIL))
        if backlog:
            BACKLOG.unlink(missing_ok=True)


def _write_or_park(records: list[dict]) -> None:
    """Never let the audit trail crash an agent run: if the file stays locked,
    park the records in the backlog so the next write adds them."""
    try:
        _write(records)
    except Exception as exc:
        try:
            with _lock, BACKLOG.open("a", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        except Exception:
            print(f"AUDIT WRITE FAILED ({type(exc).__name__}: {exc}); records: {records}", file=sys.stderr)


async def log(event: str, deps, **fields: Any) -> None:
    """Append one record. deps is the TeamDeps of the agent doing the step."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "run_id": deps.run_id,
        "ticket_id": deps.ticket_id,
        "agent": deps.agent,
        "chain": deps.chain + [deps.agent],
        "event": event,
        **_clean(fields),
    }
    await asyncio.to_thread(_write_or_park, [record])

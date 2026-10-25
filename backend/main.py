"""Campus Customs backend: the routes the React dashboard calls.

Start it from the backend/ folder:

    uvicorn main:app --reload --port 8000

Every shop fact and every change goes through the Campus Customs MCP server;
this file never opens the database itself (reset is a whole-file copy).
Agents only *request* payments. POST /api/payments/{id}/approve is the one
route that moves money, and the MCP server refuses anything that would push
cash below zero.
"""

from __future__ import annotations

import asyncio
import sys
import threading
from concurrent.futures import Future
from datetime import datetime, timezone
from pathlib import Path

# Works whether uvicorn is started from backend/ ("main:app") or the project root ("backend.main:app").
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))



from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend import audit, reset_db  # noqa: E402
from backend.config import MODEL_NAME, build_mcp_toolset  # noqa: E402
from backend.models import TeamDeps  # noqa: E402
from backend.team import run_ticket  # noqa: E402

app = FastAPI(title="Campus Customs Multi-Agent Operations", version="1.0")

# Let the React dev server (Vite, any localhost port) call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# All MCP and agent work runs on one background event loop. On Windows that
# loop must be a Proactor loop so the MCP server subprocess can start, which
# isn't guaranteed for uvicorn's own loop under --reload.
# ---------------------------------------------------------------------------

class _Worker:
    def __init__(self) -> None:
        factory = getattr(asyncio, "ProactorEventLoop", asyncio.new_event_loop)
        self.loop: asyncio.AbstractEventLoop = factory()
        threading.Thread(target=self.loop.run_forever, daemon=True, name="agent-loop").start()

    def submit(self, coro) -> Future:
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    async def run(self, coro):
        return await asyncio.wrap_future(self.submit(coro))


WORKER = _Worker()
RUNS: dict[str, dict] = {}       # run_id -> status/result, newest kept in memory
_active_ticket: dict = {"id": None}  # one team run at a time (protects cash and tokens)


async def _mcp(tool: str, **args) -> dict:
    client = build_mcp_toolset().client
    async with client:
        result = await client.call_tool(tool, args)
    return result.structured_content or {}


async def mcp(tool: str, **args) -> dict:
    return await WORKER.run(_mcp(tool, **args))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------- routes

@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "model": MODEL_NAME, "busy_ticket": _active_ticket["id"]}


@app.get("/api/tickets")
async def tickets() -> dict:
    """The three tickets and whether each is open or resolved."""
    data = await mcp("list_tickets")
    for t in data.get("tickets", []):
        t["state"] = "resolved" if t["status"] == "resolved" else "open"
    return data


class RunRequest(BaseModel):
    wait: bool = Field(False, description="True = hold the request until the team finishes.")


async def _run_and_record(run_key: str, ticket_id: int) -> dict:
    try:
        out = await run_ticket(ticket_id)
        # The team's work is done: mark the ticket resolved on the board. Payments it
        # filed stay pending until a human approves them.
        decision = out["output"].get("decision", "done")
        await _mcp("update_ticket_status", ticket_id=ticket_id, status="resolved",
                   note=f"Team run {out['run_id']} finished; Boss decision: {decision}.", updated_by="desk")
        RUNS[run_key].update(status="done", finished_at=_now(), result=out, run_id=out["run_id"])
    except Exception as exc:
        RUNS[run_key].update(status="failed", finished_at=_now(), error=f"{type(exc).__name__}: {exc}")
    finally:
        _active_ticket["id"] = None
    return RUNS[run_key]


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_team(ticket_id: int, body: RunRequest | None = None) -> dict:
    """Run the agent team (Boss first) on one ticket. Returns at once unless wait=true;
    the dashboard follows progress through /api/events."""
    found = await mcp("get_ticket", ticket_id=ticket_id)
    if not found.get("found"):
        raise HTTPException(404, f"No ticket {ticket_id}.")
    if _active_ticket["id"] is not None:
        raise HTTPException(409, f"The team is already working ticket {_active_ticket['id']}. Try again when it finishes.")
    _active_ticket["id"] = ticket_id
    run_key = f"t{ticket_id}-{datetime.now(timezone.utc):%H%M%S%f}"
    RUNS[run_key] = {"run_key": run_key, "ticket_id": ticket_id, "status": "running", "started_at": _now()}
    future = WORKER.submit(_run_and_record(run_key, ticket_id))
    if body and body.wait:
        return await asyncio.wrap_future(future)
    return RUNS[run_key]


@app.get("/api/runs/{run_key}")
async def run_status(run_key: str) -> dict:
    """Status of one team run started by POST /api/tickets/{id}/run (running, done or failed)."""
    if run_key not in RUNS:
        raise HTTPException(404, "Unknown run.")
    return RUNS[run_key]


def _summarize(rec: dict) -> dict:
    """Trim an audit record to what the board shows: who, what they said, which tools."""
    out = {k: rec.get(k) for k in ("ts", "run_id", "ticket_id", "agent", "chain", "event")}
    ev = rec.get("event")
    if ev == "loop_step" and rec.get("phase") == "model_replied":
        out["said"] = rec.get("text")
        out["tools_used"] = [c["tool"] for c in rec.get("tool_calls", [])]
        out["tool_calls"] = rec.get("tool_calls", [])
        out["tokens"] = rec.get("tokens")
    elif ev == "loop_step":
        out["tool_results"] = [{"tool": r["tool"], "result": r["result"][:400]} for r in rec.get("tool_results", [])]
    elif ev in ("handoff", "handoff_refused"):
        out.update(to_agent=rec.get("to_agent"), task=rec.get("task"), reason=rec.get("reason"))
    elif ev in ("agent_start", "run_start"):
        out["task"] = rec.get("task")
    elif ev in ("agent_done", "run_end"):
        out["output"] = rec.get("output")
        out["usage"] = rec.get("usage")
    else:
        out.update({k: v for k, v in rec.items() if k not in out})
    return out


@app.get("/api/events")
async def events(limit: int = 50, ticket_id: int | None = None, run_id: str | None = None) -> dict:
    """Recent agent events, newest last: what each agent said and which tools it used."""
    records = await asyncio.to_thread(audit.read_all)
    if ticket_id is not None:
        records = [r for r in records if r.get("ticket_id") == ticket_id]
    if run_id:
        records = [r for r in records if r.get("run_id") == run_id]
    picked = records[-max(1, min(limit, 500)):]
    return {"events": [_summarize(r) for r in picked], "count": len(picked), "total_in_trail": len(records)}


@app.get("/api/payments")
async def payments(status: str = "pending") -> dict:
    """Payment and purchase requests the agents filed (default: waiting for a human)."""
    if status not in ("pending", "paid", "rejected", "all"):
        raise HTTPException(400, "status must be pending, paid, rejected or all")
    return await mcp("list_payment_requests", status=status)


class Approval(BaseModel):
    approver: str = Field(..., min_length=2, description="The human approving; agents can't approve.")


@app.post("/api/payments/{request_id}/approve")
async def approve(request_id: int, body: Approval) -> dict:
    """A human approves a payment or purchase. The ONLY route that changes cash;
    the MCP server refuses it if cash would go negative or the bill is closed."""
    out = await mcp("approve_and_pay", request_id=request_id, approver=body.approver)
    await audit.log("human_approve", TeamDeps(agent="human"), request_id=request_id,
                    approver=body.approver, result=out)
    if not out.get("paid"):
        raise HTTPException(409, out.get("refused", "Payment refused."))
    return out


class Rejection(Approval):
    note: str = ""


@app.post("/api/payments/{request_id}/reject")
async def reject(request_id: int, body: Rejection) -> dict:
    """A human rejects a payment request. No money moves."""
    out = await mcp("reject_payment", request_id=request_id, approver=body.approver, note=body.note)
    await audit.log("human_reject", TeamDeps(agent="human"), request_id=request_id,
                    approver=body.approver, result=out)
    if not out.get("rejected"):
        raise HTTPException(409, out.get("refused", "Rejection refused."))
    return out


@app.get("/api/cash")
async def cash() -> dict:
    """Current checking balance from cash_accounts (plus pending requests for context)."""
    pos = await mcp("get_cash_position")
    checking = next((a for a in pos.get("cash_accounts", []) if a["name"] == "checking"), None)
    return {
        "account": "checking",
        "balance": checking["balance"] if checking else None,
        "as_of": checking["date"] if checking else None,
        "pending_total": pos.get("pending_total"),
        "balance_if_all_pending_paid": pos.get("cash_left_if_all_pending_paid"),
        "source": "cash_accounts",
    }


@app.post("/api/reset")
async def reset() -> dict:
    """Restore data/campus_customs_new.db from the untouched original for a fresh run.
    The original file is only read, and the audit trail is never wiped."""
    if _active_ticket["id"] is not None:
        raise HTTPException(409, f"Can't reset while the team is working ticket {_active_ticket['id']}.")
    digest = await asyncio.to_thread(reset_db.reset)
    await audit.log("database_reset", TeamDeps(agent="human"),
                    copied_from=reset_db.ORIGINAL.name, copied_to=reset_db.WORKING.name, sha256=digest)
    return {"reset": True, "from": "data/campus_customs.db", "to": "data/campus_customs_new.db",
            "sha256": digest, "audit_trail_kept": True}

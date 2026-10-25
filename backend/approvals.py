"""Human approval desk. Agents can only REQUEST payments; a person approves here.

    python -m backend.approvals list
    python -m backend.approvals approve 1 --by "Your Name"
    python -m backend.approvals reject 2 --by "Your Name" --note "wait a week"

This calls the same Campus Customs MCP server (approve_and_pay / reject_payment),
so the money rules (cash never negative, bill still open) are enforced in one
place. Those two tools are never given to an agent. Every decision is appended
to output/audit_trail.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from fastmcp import Client

from backend import audit
from backend.config import build_mcp_toolset
from backend.models import TeamDeps


async def call(tool: str, **args) -> dict:
    client: Client = build_mcp_toolset().client
    async with client:
        result = await client.call_tool(tool, args)
    return result.structured_content or {}


async def main_async(args) -> dict:
    if args.cmd == "list":
        return await call("list_payment_requests", status="pending")
    deps = TeamDeps(agent="human", ticket_id=None)
    if args.cmd == "approve":
        out = await call("approve_and_pay", request_id=args.request_id, approver=args.by)
    else:
        out = await call("reject_payment", request_id=args.request_id, approver=args.by, note=args.note or "")
    await audit.log(f"human_{args.cmd}", deps, request_id=args.request_id, approver=args.by, result=out)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Approve or reject payment requests (humans only).")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for name in ("approve", "reject"):
        s = sub.add_parser(name)
        s.add_argument("request_id", type=int)
        s.add_argument("--by", required=True, help="your name: the human approver")
        if name == "reject":
            s.add_argument("--note", default="")
    print(json.dumps(asyncio.run(main_async(p.parse_args())), indent=2, default=str))


if __name__ == "__main__":
    main()

"""Run the Campus Customs team.

    python -m backend.team --ticket 101
    python -m backend.team --agent inventory "Check CC-HOOD-NAVY size M for 20 units (ticket 103)."

The Boss starts every ticket run; any agent can hand off to any other.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from backend import audit
from backend.agents import AGENTS, run_agent
from backend.config import MAX_DELEGATIONS_PER_RUN, MAX_HANDOFF_DEPTH, MODEL_NAME, SHOP_TOOLS
from backend.models import RunBudget, TeamDeps


def new_deps(agent: str, ticket_id: int | None = None) -> TeamDeps:
    budget = RunBudget(max_delegations=MAX_DELEGATIONS_PER_RUN, max_depth=MAX_HANDOFF_DEPTH)
    return TeamDeps(ticket_id=ticket_id, agent=agent, budget=budget)


async def run_task(agent: str, task: str, ticket_id: int | None = None) -> dict:
    """Run one agent (it may hand off to others) and return its output plus usage."""
    deps = new_deps(agent, ticket_id)
    await audit.log("run_start", deps, model=MODEL_NAME, task=task,
                    limits={"handoffs": deps.budget.max_delegations, "depth": deps.budget.max_depth})
    try:
        async with SHOP_TOOLS:  # one MCP server process for the whole run
            result = await run_agent(agent, task, deps)
    except Exception as exc:
        await audit.log("run_failed", deps, error=f"{type(exc).__name__}: {exc}")
        raise
    await audit.log("run_end", deps, handoffs=deps.budget.delegations,
                    usage={"requests": deps.budget.requests, "input_tokens": deps.budget.input_tokens,
                           "output_tokens": deps.budget.output_tokens})
    return {
        "run_id": deps.run_id,
        "model": MODEL_NAME,
        "agent": agent,
        "output": result.output.model_dump(),
        "handoffs": deps.budget.delegations,
        "usage": {
            "requests": deps.budget.requests,
            "input_tokens": deps.budget.input_tokens,
            "output_tokens": deps.budget.output_tokens,
        },
    }


async def run_ticket(ticket_id: int) -> dict:
    """The Boss works one ticket end to end."""
    task = (f"Work ticket {ticket_id}. Look it up, hand work to the right specialists, "
            f"and return your final decision.")
    return await run_task("boss", task, ticket_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Campus Customs agent team.")
    parser.add_argument("--ticket", type=int, help="ticket id for the Boss to work")
    parser.add_argument("--agent", choices=sorted(AGENTS), help="run one agent directly")
    parser.add_argument("task", nargs="?", help="task text when using --agent")
    args = parser.parse_args()
    if args.agent:
        out = asyncio.run(run_task(args.agent, args.task or "", args.ticket))
    elif args.ticket:
        out = asyncio.run(run_ticket(args.ticket))
    else:
        parser.error("use --ticket ID or --agent NAME 'task'")
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()

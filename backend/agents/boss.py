"""Boss: reads each ticket, routes work to the specialists and makes the final call.

Prompt: backend/prompts/boss.md    Output type: BossDecision (backend/models.py)
Tools: Campus Customs MCP server + hand_off to any teammate.
"""

from backend.agents._base import make_agent, run_agent
from backend.models import BossDecision, TeamDeps

ROLE = "boss"

boss_agent = make_agent(ROLE, BossDecision)


async def run_boss(task: str, deps: TeamDeps | None = None):
    """Run the boss agent loop on one task and return its result (BossDecision)."""
    return await run_agent(ROLE, task, deps)

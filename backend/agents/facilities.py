"""Facilities: handles the shop space (leases, rent).

Prompt: backend/prompts/facilities.md    Output type: FacilitiesReport (backend/models.py)
Tools: Campus Customs MCP server + hand_off to any teammate.
"""

from backend.agents._base import make_agent, run_agent
from backend.models import FacilitiesReport, TeamDeps

ROLE = "facilities"

facilities_agent = make_agent(ROLE, FacilitiesReport)


async def run_facilities(task: str, deps: TeamDeps | None = None):
    """Run the facilities agent loop on one task and return its result (FacilitiesReport)."""
    return await run_agent(ROLE, task, deps)

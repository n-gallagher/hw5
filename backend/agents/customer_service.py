"""Customer Service: drafts messages for customers. Drafts stay on the board.

Prompt: backend/prompts/customer_service.md    Output type: CustomerDraft (backend/models.py)
Tools: Campus Customs MCP server + hand_off to any teammate.
"""

from backend.agents._base import make_agent, run_agent
from backend.models import CustomerDraft, TeamDeps

ROLE = "customer_service"

customer_service_agent = make_agent(ROLE, CustomerDraft)


async def run_customer_service(task: str, deps: TeamDeps | None = None):
    """Run the customer_service agent loop on one task and return its result (CustomerDraft)."""
    return await run_agent(ROLE, task, deps)

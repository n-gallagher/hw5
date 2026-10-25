"""Accounting: watches cash and invoices, checks margins, prepares payments for human approval.

Prompt: backend/prompts/accounting.md    Output type: AccountingReport (backend/models.py)
Tools: Campus Customs MCP server + hand_off to any teammate.
"""

from backend.agents._base import make_agent, run_agent
from backend.models import AccountingReport, TeamDeps

ROLE = "accounting"

accounting_agent = make_agent(ROLE, AccountingReport)


async def run_accounting(task: str, deps: TeamDeps | None = None):
    """Run the accounting agent loop on one task and return its result (AccountingReport)."""
    return await run_agent(ROLE, task, deps)

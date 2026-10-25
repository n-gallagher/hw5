"""Inventory: checks stock by SKU and size, spots shortfalls, finds the restock vendor.

Prompt: backend/prompts/inventory.md    Output type: InventoryReport (backend/models.py)
Tools: Campus Customs MCP server + hand_off to any teammate.
"""

from backend.agents._base import make_agent, run_agent
from backend.models import InventoryReport, TeamDeps

ROLE = "inventory"

inventory_agent = make_agent(ROLE, InventoryReport)


async def run_inventory(task: str, deps: TeamDeps | None = None):
    """Run the inventory agent loop on one task and return its result (InventoryReport)."""
    return await run_agent(ROLE, task, deps)

"""The five Campus Customs agents, one file per role. Importing this package builds them all."""

from backend.agents.boss import boss_agent, run_boss
from backend.agents.inventory import inventory_agent, run_inventory
from backend.agents.accounting import accounting_agent, run_accounting
from backend.agents.facilities import facilities_agent, run_facilities
from backend.agents.customer_service import customer_service_agent, run_customer_service
from backend.agents._base import AGENTS, run_agent

__all__ = [
    "AGENTS", "run_agent",
    "boss_agent", "run_boss",
    "inventory_agent", "run_inventory",
    "accounting_agent", "run_accounting",
    "facilities_agent", "run_facilities",
    "customer_service_agent", "run_customer_service",
]

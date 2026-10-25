"""Shared settings: the one model every agent uses, and the MCP connection.

Rule for this homework: every agent runs gpt-6-luna through Portkey. The model
name lives here only, so no other model can creep into the code.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport
from openai import AsyncOpenAI
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
PROMPTS_DIR = BACKEND_DIR / "prompts"

# Key lives in .env in the project folder or one level up; never in code.
load_dotenv(PROJECT_DIR / ".env")
load_dotenv(PROJECT_DIR.parent / ".env")

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

MODEL_NAME = "gpt-6-luna"  # the ONLY model allowed in this project
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# Limits that keep token use in check.
AGENT_USAGE_LIMITS = UsageLimits(request_limit=8, tool_calls_limit=12)  # one agent's loop
MAX_DELEGATIONS_PER_RUN = 12  # hand-offs across the whole team for one ticket
MAX_HANDOFF_DEPTH = 4         # boss -> a -> b -> c, no deeper

AUDIT_TRAIL = PROJECT_DIR / "output" / "audit_trail.json"

# Least privilege: each agent sees only the MCP tools its job needs.
# approve_and_pay and reject_payment are for humans and no agent ever gets them.
HUMAN_ONLY_TOOLS = frozenset({"approve_and_pay", "reject_payment"})
AGENT_TOOLS: dict[str, frozenset[str]] = {
    "boss": frozenset({"get_today", "list_open_tickets", "get_ticket", "get_cash_position",
                       "list_payment_requests", "update_ticket_status"}),
    "inventory": frozenset({"get_today", "get_ticket", "check_stock", "list_vendors", "check_vendor_hold"}),
    "accounting": frozenset({"get_today", "get_ticket", "get_cash_position", "get_invoice", "get_rent_due",
                             "check_discount", "check_vendor_hold", "list_payment_requests", "request_payment"}),
    "facilities": frozenset({"get_today", "get_ticket", "get_rent_due", "get_cash_position"}),
    "customer_service": frozenset({"get_today", "get_ticket", "post_draft"}),
}
assert not any(HUMAN_ONLY_TOOLS & tools for tools in AGENT_TOOLS.values())


def build_model() -> OpenAIResponsesModel:
    """gpt-6-luna through Portkey (Responses API, needed for function tools)."""
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is missing. Put it in .env (see .env.example).")
    client = AsyncOpenAI(api_key=api_key, base_url=PORTKEY_BASE_URL)
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


def _mcp_python() -> str:
    """Use the MCP server's own venv if it exists, else the current Python."""
    win = PROJECT_DIR / "mcp_server" / ".venv" / "Scripts" / "python.exe"
    nix = PROJECT_DIR / "mcp_server" / ".venv" / "bin" / "python"
    for p in (win, nix):
        if p.exists():
            return str(p)
    import sys
    return sys.executable


def build_mcp_toolset() -> MCPToolset:
    """All shop facts come from the Campus Customs MCP server (stdio)."""
    transport = PythonStdioTransport(
        script_path=PROJECT_DIR / "mcp_server" / "server.py",
        python_cmd=_mcp_python(),
        cwd=str(PROJECT_DIR),
    )
    return MCPToolset(Client(transport), id="campus-customs")


MODEL = build_model()
SHOP_TOOLS = build_mcp_toolset()  # one shared connection for the whole team

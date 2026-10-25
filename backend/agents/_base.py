"""What every Campus Customs agent shares: the model, its slice of the MCP
shop tools, the hand-off tool (full connectivity) and the audited agent loop.
"""

from __future__ import annotations

from dataclasses import replace

from pydantic import BaseModel
from pydantic_ai import Agent, FunctionToolset, RunContext
from pydantic_ai.messages import (
    RetryPromptPart, TextPart, ThinkingPart, ToolCallPart, ToolReturnPart, UserPromptPart,
)

from backend import audit
from backend.config import AGENT_TOOLS, AGENT_USAGE_LIMITS, HUMAN_ONLY_TOOLS, MODEL, MODEL_NAME, PROMPTS_DIR, SHOP_TOOLS
from backend.models import AGENT_NAMES, AgentName, TeamDeps

AGENTS: dict[AgentName, Agent[TeamDeps, BaseModel]] = {}

HANDOFF_TOOLS: FunctionToolset[TeamDeps] = FunctionToolset()


@HANDOFF_TOOLS.tool
async def hand_off(ctx: RunContext[TeamDeps], to_agent: AgentName, task: str) -> str:
    """Hand a focused task to a teammate and get their structured report back.

    to_agent: one of boss, inventory, accounting, facilities, customer_service.
    task: one clear request with the facts they need (ticket id, SKU, size,
    quantity, invoice id, lease id). Any agent may hand off to any other.
    You cannot hand off to yourself or to anyone already working on this
    chain (that would loop), and each ticket has a hand-off budget.
    """
    deps = ctx.deps
    me = deps.agent
    refusal = None
    if to_agent not in AGENT_NAMES:
        refusal = f"unknown agent '{to_agent}'. Choose from {', '.join(AGENT_NAMES)}."
    elif to_agent == me:
        refusal = "you cannot hand off to yourself. Do the work or hand it to someone else."
    elif to_agent in deps.chain:
        refusal = (f"{to_agent} is already working on this chain "
                   f"({' -> '.join(deps.chain + [me])}). Answer with what you have.")
    elif len(deps.chain) + 1 >= deps.budget.max_depth:
        refusal = f"hand-off depth limit ({deps.budget.max_depth}) reached. Answer with what you have."
    elif deps.budget.delegations >= deps.budget.max_delegations:
        refusal = f"hand-off budget ({deps.budget.max_delegations}) for this ticket is used up. Answer with what you have."
    if refusal:
        await audit.log("handoff_refused", deps, to_agent=to_agent, task=task, reason=refusal)
        return f"REFUSED: {refusal}"

    deps.budget.delegations += 1
    await audit.log("handoff", deps, to_agent=to_agent, task=task,
                    handoffs_used=deps.budget.delegations, handoff_budget=deps.budget.max_delegations)
    child = replace(deps, agent=to_agent, chain=deps.chain + [me])
    framed = f"Hand-off from {me} (ticket {deps.ticket_id}):\n{task}"
    try:
        result = await run_agent(to_agent, framed, child)
    except Exception as exc:  # a failed teammate reports back instead of crashing the run
        return f"ERROR from {to_agent}: {type(exc).__name__}: {exc}"
    return result.output.model_dump_json()


def load_prompt(name: AgentName) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def make_agent(name: AgentName, output_type: type[BaseModel]) -> Agent[TeamDeps, BaseModel]:
    """Build one role: its own prompt file and output type, the shared model,
    only the MCP tools on its allow-list, and the hand-off tool."""
    allowed = AGENT_TOOLS[name]
    shop_tools = SHOP_TOOLS.filtered(
        lambda ctx, tool, allowed=allowed: tool.name in allowed and tool.name not in HUMAN_ONLY_TOOLS
    )
    agent = Agent(
        MODEL,
        name=name,
        instructions=load_prompt(name),
        deps_type=TeamDeps,
        output_type=output_type,
        toolsets=[shop_tools, HANDOFF_TOOLS],
        retries=2,
    )
    AGENTS[name] = agent
    return agent


def _response_record(resp) -> dict:
    calls, text, thinking = [], [], []
    for part in resp.parts:
        if isinstance(part, ToolCallPart):
            calls.append({"tool": part.tool_name, "args": part.args_as_dict(), "call_id": part.tool_call_id})
        elif isinstance(part, TextPart):
            text.append(part.content)
        elif isinstance(part, ThinkingPart) and part.content:
            thinking.append(part.content)
    u = resp.usage
    return {
        "model": MODEL_NAME,  # the model we requested (the only one allowed)
        "provider_deployment": resp.model_name,  # Portkey's label for it, e.g. gpt-6-luna-global
        "tool_calls": calls,
        "text": "\n".join(text) or None,
        "reasoning": "\n".join(thinking) or None,
        "finish_reason": resp.finish_reason,
        "tokens": {"input": u.input_tokens, "output": u.output_tokens,
                   "cached": getattr(u, "cache_read_tokens", 0)},
    }


def _request_record(req) -> dict:
    returns, retries, prompt = [], [], None
    for part in req.parts:
        if isinstance(part, ToolReturnPart):
            returns.append({"tool": part.tool_name, "call_id": part.tool_call_id, "result": part.model_response_str()})
        elif isinstance(part, RetryPromptPart):
            retries.append({"tool": part.tool_name, "problem": part.model_response()})
        elif isinstance(part, UserPromptPart):
            prompt = part.content if isinstance(part.content, str) else str(part.content)
    return {"task": prompt, "tool_results": returns, "retries": retries}


async def run_agent(name: AgentName, task: str, deps: TeamDeps | None = None):
    """The agent loop, one audited step at a time: send the task, the model
    answers with tool calls or a final output, tools run, repeat until the
    output type is filled or the per-agent usage limit stops it."""
    deps = replace(deps or TeamDeps(), agent=name)
    agent = AGENTS[name]
    await audit.log("agent_start", deps, model=MODEL_NAME, task=task,
                    tools=sorted(AGENT_TOOLS[name]) + ["hand_off"])
    step = 0
    try:
        async with agent.iter(task, deps=deps, usage_limits=AGENT_USAGE_LIMITS) as run:
            async for node in run:
                if Agent.is_model_request_node(node):
                    step += 1
                    await audit.log("loop_step", deps, step=step, phase="send_to_model", **_request_record(node.request))
                elif Agent.is_call_tools_node(node):
                    await audit.log("loop_step", deps, step=step, phase="model_replied", **_response_record(node.model_response))
        result = run.result
    except Exception as exc:
        await audit.log("agent_error", deps, step=step, error=f"{type(exc).__name__}: {exc}")
        raise
    usage = result.usage
    deps.budget.requests += usage.requests
    deps.budget.input_tokens += usage.input_tokens or 0
    deps.budget.output_tokens += usage.output_tokens or 0
    await audit.log("agent_done", deps, steps=step, output=result.output.model_dump(mode="json"),
                    usage={"requests": usage.requests, "input_tokens": usage.input_tokens,
                           "output_tokens": usage.output_tokens, "tool_calls": usage.tool_calls})
    return result

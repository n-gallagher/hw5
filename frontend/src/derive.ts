// Turn the raw audit events from /api/events into what the desk shows:
// the latest run, each agent's state, a feed line per step, and a summary.
import type { AgentName, DeskEvent } from "./api";
import { houseOf } from "./houses";

export function latestRun(events: DeskEvent[]): DeskEvent[] {
  const starts = events.filter((e) => e.event === "run_start");
  if (!starts.length) return [];
  const runId = starts[starts.length - 1].run_id;
  return events.filter((e) => e.run_id === runId);
}

export type AgentStatus = "idle" | "working" | "done" | "error";

export interface AgentState {
  status: AgentStatus;
  doing: string;
  tools: string[];
  steps: number;
}

const HIDDEN_TOOLS = new Set(["final_result"]);

function args(a: Record<string, unknown>): string {
  return Object.entries(a)
    .filter(([k]) => !["requested_by", "updated_by", "author"].includes(k))
    .map(([k, v]) => `${k}=${typeof v === "string" ? (v.length > 28 ? v.slice(0, 28) + "…" : v) : JSON.stringify(v)}`)
    .join(", ");
}

export function agentStates(run: DeskEvent[]): Partial<Record<AgentName, AgentState>> {
  const out: Partial<Record<AgentName, AgentState>> = {};
  for (const e of run) {
    const a = e.agent as AgentName;
    if (!houseOf(a)) continue;
    const s = (out[a] ??= { status: "idle", doing: "", tools: [], steps: 0 });
    if (e.event === "agent_start") { s.status = "working"; s.doing = "Taking up the task"; }
    if (e.event === "loop_step" && e.tool_calls) {
      s.steps += 1;
      const calls = e.tool_calls.filter((c) => !HIDDEN_TOOLS.has(c.tool));
      for (const c of calls) if (c.tool !== "hand_off" && !s.tools.includes(c.tool)) s.tools.push(c.tool);
      if (calls.length) {
        const c = calls[calls.length - 1];
        s.doing = c.tool === "hand_off" ? `Handing off to ${houseOf(String(c.args.to_agent))?.role ?? c.args.to_agent}` : `Calling ${c.tool}`;
      } else if (e.tool_calls.some((c) => c.tool === "final_result")) {
        s.doing = "Writing its report";
      }
    }
    if (e.event === "handoff") s.doing = `Waiting on ${houseOf(String(e.to_agent))?.role ?? e.to_agent}`;
    if (e.event === "agent_done") { s.status = "done"; s.doing = "Reported back"; }
    if (e.event === "agent_error") { s.status = "error"; s.doing = e.error ?? "Error"; }
  }
  return out;
}

export interface FeedLine {
  key: string;
  ts: string;
  agent: AgentName | "desk";
  kind: "start" | "tool" | "result" | "say" | "handoff" | "refused" | "done" | "end" | "error";
  text: string;
  detail?: string;
}

export function feed(run: DeskEvent[]): FeedLine[] {
  const lines: FeedLine[] = [];
  run.forEach((e, i) => {
    const agent = (houseOf(e.agent) ? e.agent : "desk") as FeedLine["agent"];
    const k = `${e.ts}-${i}`;
    switch (e.event) {
      case "run_start":
        lines.push({ key: k, ts: e.ts, agent: "desk", kind: "start", text: `The desk opens ticket ${e.ticket_id}. The Boss is summoned.` });
        break;
      case "agent_start":
        if (e.agent !== "boss") lines.push({ key: k, ts: e.ts, agent, kind: "start", text: "takes up the task", detail: e.task?.replace(/^Hand-off from \w+ \(ticket \d+\):\n/, "") });
        break;
      case "handoff":
        lines.push({ key: k, ts: e.ts, agent, kind: "handoff", text: `hands off to ${houseOf(String(e.to_agent))?.role ?? e.to_agent}`, detail: e.task });
        break;
      case "handoff_refused":
        lines.push({ key: k, ts: e.ts, agent, kind: "refused", text: `hand-off to ${houseOf(String(e.to_agent))?.role ?? e.to_agent} blocked`, detail: e.reason ?? undefined });
        break;
      case "loop_step":
        if (e.tool_calls) {
          if (e.said) lines.push({ key: k + "s", ts: e.ts, agent, kind: "say", text: e.said });
          e.tool_calls.filter((c) => !HIDDEN_TOOLS.has(c.tool) && c.tool !== "hand_off").forEach((c, j) =>
            lines.push({ key: `${k}-${j}`, ts: e.ts, agent, kind: "tool", text: c.tool, detail: args(c.args) }));
        } else if (e.tool_results?.length) {
          e.tool_results.filter((r) => !HIDDEN_TOOLS.has(r.tool) && r.tool !== "hand_off").forEach((r, j) =>
            lines.push({ key: `${k}-r${j}`, ts: e.ts, agent, kind: "result", text: r.tool, detail: r.result }));
        }
        break;
      case "agent_done":
        lines.push({ key: k, ts: e.ts, agent, kind: "done", text: "reports back", detail: reportLine(e.agent as AgentName, e.output ?? {}) });
        break;
      case "agent_error":
        lines.push({ key: k, ts: e.ts, agent, kind: "error", text: "hit an error", detail: e.error });
        break;
      case "run_end":
        lines.push({ key: k, ts: e.ts, agent: "desk", kind: "end", text: "The team is finished. Ticket marked resolved." });
        break;
    }
  });
  return lines;
}

/** One plain sentence per agent's structured report. */
export function reportLine(agent: AgentName, o: Record<string, unknown>): string {
  const s = (v: unknown) => (typeof v === "string" ? v : "");
  switch (agent) {
    case "boss": return s(o.rationale) || s(o.ask_summary);
    case "inventory": return s(o.summary);
    case "accounting": return s(o.recommendation);
    case "facilities": return s(o.summary);
    case "customer_service": return o.subject ? `Drafted “${s(o.subject)}” for ${s(o.recipient)}. ${s(o.status)}` : "";
  }
}

export interface Summary {
  decision?: string;
  ask?: string;
  usage?: { requests: number; input_tokens: number; output_tokens: number };
  agents: { agent: AgentName; line: string; tools: string[]; handedTo: string[] }[];
  draft?: { recipient: string; subject: string; body: string };
  nextSteps: string[];
}

export function summarize(run: DeskEvent[]): Summary | null {
  const end = run.find((e) => e.event === "run_end");
  if (!end) return null;
  const states = agentStates(run);
  const done = run.filter((e) => e.event === "agent_done");
  const bossOut = done.filter((e) => e.agent === "boss").pop()?.output ?? {};
  const csOut = done.filter((e) => e.agent === "customer_service").pop()?.output as Record<string, string> | undefined;
  const seen: AgentName[] = [];
  for (const e of done) if (!seen.includes(e.agent as AgentName)) seen.push(e.agent as AgentName);
  // Boss first, then in the order they finished
  seen.sort((a, b) => (a === "boss" ? -1 : b === "boss" ? 1 : 0));
  return {
    decision: String(bossOut.decision ?? ""),
    ask: String(bossOut.ask_summary ?? ""),
    usage: end.usage,
    agents: seen.map((a) => ({
      agent: a,
      line: reportLine(a, done.filter((e) => e.agent === a).pop()?.output ?? {}),
      tools: states[a]?.tools ?? [],
      handedTo: run.filter((e) => e.event === "handoff" && e.agent === a).map((e) => houseOf(String(e.to_agent))?.role ?? String(e.to_agent)),
    })),
    draft: csOut?.body ? { recipient: csOut.recipient, subject: csOut.subject, body: csOut.body } : undefined,
    nextSteps: Array.isArray(bossOut.next_steps) ? (bossOut.next_steps as string[]) : [],
  };
}

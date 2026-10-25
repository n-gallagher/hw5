// Typed calls to the FastAPI backend from Problem 7.
export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type AgentName = "boss" | "inventory" | "accounting" | "facilities" | "customer_service";

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  lease_id: number | null;
  invoice_id: number | null;
  status: string;
  state: "open" | "resolved";
  notes: string | null;
  created_at: string;
}

export interface ToolCall { tool: string; args: Record<string, unknown>; call_id?: string }

export interface DeskEvent {
  ts: string;
  run_id: string;
  ticket_id: number | null;
  agent: AgentName | "human";
  chain: string[];
  event: string;
  task?: string;
  said?: string | null;
  tools_used?: string[];
  tool_calls?: ToolCall[];
  tool_results?: { tool: string; result: string }[];
  tokens?: { input: number; output: number };
  to_agent?: AgentName;
  reason?: string | null;
  output?: Record<string, unknown> | null;
  usage?: { requests: number; input_tokens: number; output_tokens: number };
  error?: string;
}

export interface RunState {
  run_key: string;
  ticket_id: number;
  status: "running" | "done" | "failed";
  started_at: string;
  finished_at?: string;
  run_id?: string;
  error?: string;
}

export interface PaymentRequest {
  id: number;
  ticket_id: number | null;
  kind: "invoice" | "rent" | "purchase_order";
  ref_id: number | null;
  payee: string;
  amount: number;
  sku: string | null;
  size: string | null;
  qty: number | null;
  reason: string;
  requested_by: string;
  status: string;
  created_at: string;
}

export interface Payment { id: number; kind: string; ref_id: number; amount: number; account: string; paid_at: string; approved_by: string }

export interface Cash {
  account: string;
  balance: number | null;
  as_of: string | null;
  pending_total: number;
  balance_if_all_pending_paid: number;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof body?.detail === "string" ? body.detail : `HTTP ${res.status}`;
    throw new Error(detail);
  }
  return body as T;
}

export const api = {
  health: () => call<{ ok: boolean; model: string; busy_ticket: number | null }>("/api/health"),
  tickets: () => call<{ tickets: Ticket[] }>("/api/tickets").then((d) => d.tickets),
  run: (id: number) => call<RunState>(`/api/tickets/${id}/run`, { method: "POST", body: "{}" }),
  runStatus: (key: string) => call<RunState>(`/api/runs/${key}`),
  events: (ticketId: number, limit = 400) =>
    call<{ events: DeskEvent[] }>(`/api/events?ticket_id=${ticketId}&limit=${limit}`).then((d) => d.events),
  payments: (status = "pending") =>
    call<{ payment_requests: PaymentRequest[]; payments: Payment[] }>(`/api/payments?status=${status}`),
  approve: (id: number, approver: string) =>
    call<{ paid: boolean; cash_before: number; cash_after: number; amount: number; payee: string }>(
      `/api/payments/${id}/approve`, { method: "POST", body: JSON.stringify({ approver }) }),
  reject: (id: number, approver: string, note: string) =>
    call<{ rejected: boolean }>(`/api/payments/${id}/reject`, {
      method: "POST", body: JSON.stringify({ approver, note }) }),
  cash: () => call<Cash>("/api/cash"),
  reset: () => call<{ reset: boolean }>("/api/reset", { method: "POST" }),
};

export const money = (n: number | null | undefined) =>
  n == null ? "—" : n.toLocaleString("en-US", { style: "currency", currency: "USD" });

// gpt-6-luna list prices (Lec 11 slides): $0.10 input / $0.50 output per 1M tokens
export const estCost = (input: number, output: number) => (input * 0.1 + output * 0.5) / 1e6;

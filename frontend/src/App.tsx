import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, estCost, money } from "./api";
import type { Cash, DeskEvent, PaymentRequest, Payment, RunState, Ticket } from "./api";
import { agentStates, feed, latestRun, summarize } from "./derive";
import type { FeedLine } from "./derive";
import { HOUSES, ORDER, Sigil, houseOf } from "./houses";

const TYPE_LABEL: Record<string, string> = {
  customer_order: "Customer order",
  rent_notice: "Rent notice",
  price_override: "Discount request",
};

const DECISION_LABEL: Record<string, string> = {
  fulfil: "Fulfil",
  partial_fulfil: "Partial fulfil",
  wait_for_restock: "Wait for restock",
  pay_pending_approval: "Pay, pending your approval",
  decline: "Decline",
  escalate_to_human: "Escalated to you",
};

function useInterval(fn: () => void, ms: number | null) {
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    if (ms == null) return;
    const id = setInterval(() => ref.current(), ms);
    return () => clearInterval(id);
  }, [ms]);
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [events, setEvents] = useState<DeskEvent[]>([]);
  const [run, setRun] = useState<RunState | null>(null);
  const [cash, setCash] = useState<Cash | null>(null);
  const [delta, setDelta] = useState<{ amount: number; key: number } | null>(null);
  const [pending, setPending] = useState<PaymentRequest[]>([]);
  const [ledger, setLedger] = useState<{ req: PaymentRequest[]; paid: Payment[] }>({ req: [], paid: [] });
  const [approver, setApprover] = useState<string>(() => localStorage.getItem("approver") ?? "");
  const [error, setError] = useState<string | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);
  const [sealing, setSealing] = useState<number | null>(null);
  const prevBalance = useRef<number | null>(null);

  const running = run?.status === "running";

  const loadTickets = useCallback(async () => {
    try {
      const t = await api.tickets();
      setTickets(t);
      setOnline(true);
      // ?ticket=101 opens the desk on that ticket (used for the resolved-board screenshots)
      const fromUrl = Number(new URLSearchParams(window.location.search).get("ticket"));
      setSelected((s) => s ?? (t.some((x) => x.id === fromUrl) ? fromUrl : t[0]?.id ?? null));
    } catch {
      setOnline(false);
    }
  }, []);

  const loadMoney = useCallback(async () => {
    try {
      const [c, p, all] = await Promise.all([api.cash(), api.payments("pending"), api.payments("all")]);
      if (prevBalance.current != null && c.balance != null && c.balance < prevBalance.current) {
        setDelta({ amount: prevBalance.current - c.balance, key: Date.now() });
      }
      prevBalance.current = c.balance;
      setCash(c);
      setPending(p.payment_requests);
      setLedger({ req: all.payment_requests, paid: all.payments });
    } catch { /* backend offline: the banner says so */ }
  }, []);

  const loadEvents = useCallback(async (id: number) => {
    try { setEvents(await api.events(id)); } catch { /* keep last view */ }
  }, []);

  useEffect(() => { loadTickets(); loadMoney(); }, [loadTickets, loadMoney]);
  useEffect(() => { if (selected != null) loadEvents(selected); }, [selected, loadEvents]);

  // Live: while the team works, pull new events every second and the run state.
  useInterval(() => { if (run && selected != null && run.ticket_id === selected) loadEvents(selected); }, running ? 1000 : null);
  useInterval(async () => {
    if (!run) return;
    try {
      const r = await api.runStatus(run.run_key);
      if (r.status !== "running") {
        setRun(r);
        if (r.status === "failed") setError(`Run failed: ${r.error}`);
        await Promise.all([loadTickets(), loadMoney(), loadEvents(r.ticket_id)]);
      }
    } catch (e) {
      setError(`Lost track of the run: ${(e as Error).message}`);
      setRun(null);
    }
  }, running ? 1500 : null);
  useInterval(loadMoney, running ? 5000 : 15000);

  const ticket = tickets.find((t) => t.id === selected) ?? null;
  const runEvents = useMemo(() => latestRun(events), [events]);
  const states = useMemo(() => agentStates(runEvents), [runEvents]);
  const lines = useMemo(() => feed(runEvents), [runEvents]);
  const summary = useMemo(() => summarize(runEvents), [runEvents]);
  const liveHere = running && run?.ticket_id === selected;
  const finished = runEvents.some((e) => e.event === "run_end" || e.event === "run_failed");
  const interrupted = runEvents.length > 0 && !finished && !liveHere;
  const usage = useMemo(() => {
    let i = 0, o = 0, calls = 0;
    for (const e of runEvents) if (e.event === "loop_step" && e.tokens) { i += e.tokens.input; o += e.tokens.output; calls += 1; }
    return { i, o, calls };
  }, [runEvents]);

  async function startRun() {
    if (selected == null) return;
    setError(null);
    try {
      const r = await api.run(selected);
      setRun(r);
      setEvents([]);
    } catch (e) { setError((e as Error).message); }
  }

  async function approve(p: PaymentRequest) {
    if (!approver.trim()) { setError("Add your name under “Approving as” first. Only a person can approve."); return; }
    setError(null);
    setSealing(p.id);
    try { await api.approve(p.id, approver.trim()); } catch (e) { setError((e as Error).message); }
    await Promise.all([loadMoney(), loadTickets()]);
    setSealing(null);
  }

  async function reject(p: PaymentRequest) {
    if (!approver.trim()) { setError("Add your name under “Approving as” first."); return; }
    try { await api.reject(p.id, approver.trim(), "Rejected at the desk"); } catch (e) { setError((e as Error).message); }
    await loadMoney();
  }

  async function reset() {
    if (!confirm("Reset the shop to the original database? Payments, drafts and ticket status go back to the start. The audit trail is kept.")) return;
    try {
      await api.reset();
      setRun(null); setEvents([]); prevBalance.current = null; setDelta(null);
      await Promise.all([loadTickets(), loadMoney()]);
    } catch (e) { setError((e as Error).message); }
  }

  const feedEnd = useRef<HTMLDivElement>(null);
  useEffect(() => { if (liveHere) feedEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [lines.length, liveHere]);

  return (
    <div className={`desk ${running ? "is-live" : ""}`}>
      <Grays live={running} />

      <header className="top">
        <div className="brand">
          <LetheMark />
          <div>
            <div className="kicker">Campus Customs · Multi-Agent Operations</div>
            <h1>The Lethe Desk</h1>
            <div className="motto">Five houses do the work. The ninth keeps watch, and you hold the seal.</div>
          </div>
        </div>
        <div className="top-meta">
          <span className="chip"><i className={`dot ${online ? "ok" : online === false ? "bad" : ""}`} />{online === false ? "Backend offline" : online ? "Backend live" : "Connecting…"}</span>
          <span className="chip">Desk date · 2026-08-31</span>
          <span className="chip mono">gpt-6-luna</span>
          <button className="ghost" onClick={reset} disabled={running}>Reset shop</button>
        </div>
      </header>

      {online === false && (
        <div className="banner">Can’t reach the backend at <code>http://localhost:8000</code>. Start it from <code>backend/</code> with <code>uvicorn main:app --reload --port 8000</code>.</div>
      )}
      {error && <div className="banner warn" onClick={() => setError(null)}>{error} <span className="x">dismiss</span></div>}

      <main className="grid">
        {/* ---------------- left: the board ---------------- */}
        <aside className="col left">
          <h2 className="sec">The Board <small>3 tickets</small></h2>
          <div className="tickets">
            {tickets.map((t) => {
              const isRunning = running && run?.ticket_id === t.id;
              return (
                <button key={t.id} className={`ticket ${t.id === selected ? "sel" : ""} ${t.state} ${isRunning ? "running" : ""}`}
                        onClick={() => setSelected(t.id)}>
                  <div className="t-top">
                    <span className="t-id">№ {t.id}</span>
                    {isRunning ? <span className="state live">In session</span>
                      : t.state === "resolved" ? <span className="seal" title="Resolved">R</span>
                      : <span className="state open">Open</span>}
                  </div>
                  <div className="t-subj">{t.subject}</div>
                  <div className="t-meta">{t.requester} · {TYPE_LABEL[t.type] ?? t.type}</div>
                  <div className="t-detail">
                    {t.sku ? `${t.qty} × ${t.sku} · size ${t.size}` : t.lease_id ? `Lease ${t.lease_id}` : ""}
                    {t.invoice_id ? ` · invoice ${t.invoice_id}` : ""}
                  </div>
                </button>
              );
            })}
          </div>

          <h2 className="sec">The Houses <small>your agents</small></h2>
          <div className="roster">
            {ORDER.map((a) => {
              const st = states[a];
              const h = HOUSES[a];
              return (
                <div key={a} className={`house ${interrupted && st?.status === "working" ? "idle" : st?.status ?? "idle"}`} style={{ ["--h" as string]: h.color }}>
                  <Sigil agent={a} size={30} />
                  <div className="h-text">
                    <div className="h-role">{h.role} <span className="h-house">{h.house}</span></div>
                    <div className="h-doing">{st ? (interrupted && st.status === "working" ? "Stopped: run interrupted" : st.doing) : liveHere ? "Standing by" : selected != null && runEvents.length ? "Not called on this ticket" : h.craft}</div>
                  </div>
                  <i className="lamp" />
                </div>
              );
            })}
          </div>
        </aside>

        {/* ---------------- center: the session ---------------- */}
        <section className="col center">
          {ticket ? (
            <>
              <div className="case">
                <div>
                  <div className="kicker">Ticket № {ticket.id} · {TYPE_LABEL[ticket.type] ?? ticket.type}</div>
                  <h2 className="case-title">{ticket.subject}</h2>
                  <div className="case-meta">From {ticket.requester} · “{ticket.notes?.split("\n")[0]}”</div>
                </div>
                <button className="summon" onClick={startRun} disabled={running}>
                  {liveHere ? <><span className="candle" /> The team is working…</>
                    : running ? `Team busy on № ${run?.ticket_id}`
                    : ticket.state === "resolved" ? "Run the team again" : "Start the agent team"}
                </button>
              </div>

              {summary && !liveHere && <SummaryCard summary={summary} />}

              <div className="seance">
                <div className="seance-head">
                  <h2 className="sec">Live agent activity <small>{liveHere ? "streaming" : interrupted ? "interrupted run" : runEvents.length ? "last run" : "no run yet"}</small></h2>
                  {usage.calls > 0 && (
                    <span className="meter mono">{usage.calls} model calls · {(usage.i + usage.o).toLocaleString()} tokens · ≈ ${estCost(usage.i, usage.o).toFixed(4)}</span>
                  )}
                </div>
                {lines.length === 0 ? (
                  <div className="empty">
                    {liveHere ? "Summoning the Boss…" : "Pick a ticket and start the agent team. Every step each agent takes will appear here as it happens."}
                  </div>
                ) : (
                  <ol className="feed">
                    {lines.map((l) => <Line key={l.key} l={l} />)}
                    {liveHere && <li className="line typing"><span className="dots"><i /><i /><i /></span></li>}
                    {interrupted && <li className="line k-error"><div className="l-sig"><LetheMark small /></div><div className="l-body"><div className="l-head"><b>Desk</b><span className="verb">This run stopped before it finished (the server restarted). Start the team again for a full run.</span></div></div></li>}
                  </ol>
                )}
                <div ref={feedEnd} />
              </div>
            </>
          ) : <div className="empty">Loading the board…</div>}
        </section>

        {/* ---------------- right: the vault + the seal ---------------- */}
        <aside className="col right">
          <div className="vault">
            <div className="kicker">The Vault · checking</div>
            <div className="balance">
              {money(cash?.balance)}
              {delta && <span key={delta.key} className="drop">−{money(delta.amount)}</span>}
            </div>
            <div className="v-sub">as of {cash?.as_of ?? "—"} · cash only goes out here</div>
            {cash && cash.pending_total > 0 && (
              <div className="v-pending">If everything pending is approved: <b>{money(cash.balance_if_all_pending_paid)}</b></div>
            )}
            <CashBar balance={cash?.balance ?? 0} pending={cash?.pending_total ?? 0} />
          </div>

          <div className="seal-box">
            <h2 className="sec">Awaiting your seal <small>{pending.length || "none"}</small></h2>
            <label className="approver">
              Approving as
              <input value={approver} placeholder="Your name"
                     onChange={(e) => { setApprover(e.target.value); localStorage.setItem("approver", e.target.value); }} />
            </label>
            {pending.length === 0 && <div className="empty small">No payments are waiting. When Accounting files one, it appears here for you.</div>}
            {pending.map((p) => {
              const afford = cash?.balance != null && cash.balance >= p.amount;
              return (
                <div key={p.id} className="request">
                  <div className="r-top">
                    <span className="r-kind">{p.kind === "purchase_order" ? "Purchase order" : p.kind === "rent" ? "Rent" : "Invoice"}</span>
                    <span className="r-amt">{money(p.amount)}</span>
                  </div>
                  <div className="r-payee">{p.payee}{p.ticket_id ? <span className="muted"> · ticket {p.ticket_id}</span> : null}</div>
                  <div className="r-reason">{p.reason}</div>
                  <div className="r-after">Checking after: <b className={afford ? "" : "neg"}>{money((cash?.balance ?? 0) - p.amount)}</b>{!afford && " · would go negative, will be refused"}</div>
                  <div className="r-actions">
                    <button className="approve" onClick={() => approve(p)} disabled={sealing != null}>{sealing === p.id ? "Sealing…" : "Approve & pay"}</button>
                    <button className="ghost" onClick={() => reject(p)} disabled={sealing != null}>Reject</button>
                  </div>
                  <div className="r-by">filed by {houseOf(p.requested_by)?.role ?? p.requested_by}</div>
                </div>
              );
            })}
          </div>

          {ledger.paid.length > 0 && (
            <div className="ledger">
              <h2 className="sec">Sealed payments</h2>
              {ledger.paid.map((pm) => {
                const req = ledger.req.find((r) => r.kind === pm.kind && r.ref_id === pm.ref_id && r.status === "paid");
                return (
                  <div key={pm.id} className="l-row">
                    <span>{req?.payee ?? pm.kind}</span>
                    <span className="mono">−{money(pm.amount)}</span>
                    <span className="muted small">sealed by {pm.approved_by}</span>
                  </div>
                );
              })}
            </div>
          )}
        </aside>
      </main>
      <footer className="foot">Every step is written to <code>output/audit_trail.json</code>. Agents can only request money; nothing moves without a human seal.</footer>
    </div>
  );
}

function Line({ l }: { l: FeedLine }) {
  const h = l.agent === "desk" ? null : HOUSES[l.agent];
  const time = new Date(l.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  return (
    <li className={`line k-${l.kind}`} style={{ ["--h" as string]: h?.color ?? "#9aa3b5" }}>
      <div className="l-sig">{h ? <Sigil agent={h.agent} size={26} /> : <LetheMark small />}</div>
      <div className="l-body">
        <div className="l-head">
          <b>{h ? h.role : "Desk"}</b>
          {l.kind === "tool" && <span className="verb">calls <code>{l.text}</code></span>}
          {l.kind === "result" && <span className="verb">← <code>{l.text}</code> answered</span>}
          {!["tool", "result"].includes(l.kind) && <span className="verb">{l.text}</span>}
          <span className="l-time mono">{time}</span>
        </div>
        {l.detail && <div className={`l-detail ${l.kind === "result" || l.kind === "tool" ? "mono" : ""}`}>{l.kind === "result" ? prettyResult(l.detail) : l.detail}</div>}
      </div>
    </li>
  );
}

function prettyResult(raw: string): string {
  try {
    const o = JSON.parse(raw);
    const pick = Object.entries(o).filter(([k, v]) => k !== "source" && (typeof v !== "object" || v === null)).slice(0, 7);
    return pick.map(([k, v]) => `${k}: ${v}`).join(" · ");
  } catch {
    // long results arrive cut off; pull out the simple key: value pairs we can read
    const pairs = [...raw.matchAll(/"(\w+)":\s*("([^"]{0,60})"|-?[\d.]+|true|false|null)/g)]
      .filter((m) => !["source", "found"].includes(m[1])).slice(0, 7)
      .map((m) => `${m[1]}: ${m[3] ?? m[2]}`);
    return pairs.length ? pairs.join(" · ") + " …" : raw.slice(0, 220) + "…";
  }
}

function SummaryCard({ summary }: { summary: NonNullable<ReturnType<typeof summarize>> }) {
  const u = summary.usage;
  return (
    <div className="summary">
      <div className="s-head">
        <div>
          <div className="kicker">Resolved · what each agent did</div>
          <div className="s-decision">{DECISION_LABEL[summary.decision ?? ""] ?? summary.decision}</div>
          {summary.ask && <div className="s-ask">{summary.ask}</div>}
        </div>
        <div className="wax"><span>R</span></div>
      </div>
      <div className="s-agents">
        {summary.agents.map((a) => {
          const h = HOUSES[a.agent];
          return (
            <div key={a.agent} className="s-agent" style={{ ["--h" as string]: h.color }}>
              <Sigil agent={a.agent} size={28} />
              <div>
                <div className="s-role">{h.role} <span className="h-house">{h.house}</span></div>
                <div className="s-line">{a.line || "Reported back."}</div>
                <div className="s-tools">
                  {a.tools.map((t) => <code key={t}>{t}</code>)}
                  {a.handedTo.map((t, i) => <span key={i} className="to">→ {t}</span>)}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      {summary.draft && (
        <details className="draft">
          <summary>Draft on the board for {summary.draft.recipient}: “{summary.draft.subject}” <em>(not sent)</em></summary>
          <p>{summary.draft.body}</p>
        </details>
      )}
      {u && <div className="s-usage mono">{u.requests} model calls · {u.input_tokens.toLocaleString()} in / {u.output_tokens.toLocaleString()} out · ≈ ${estCost(u.input_tokens, u.output_tokens).toFixed(4)}</div>}
    </div>
  );
}

function CashBar({ balance, pending }: { balance: number; pending: number }) {
  const start = 3400; // opening balance on the desk date
  const pct = Math.max(0, Math.min(100, (balance / start) * 100));
  const pend = Math.max(0, Math.min(pct, (pending / start) * 100));
  return (
    <div className="cashbar" title="Share of the opening $3,400 still in checking">
      <div className="fill" style={{ width: `${pct}%` }}>
        {pend > 0 && <div className="pend" style={{ width: `${(pend / pct) * 100}%` }} />}
      </div>
      <div className="cb-labels mono"><span>$0</span><span>opening $3,400</span></div>
    </div>
  );
}

function LetheMark({ small }: { small?: boolean }) {
  const s = small ? 22 : 46;
  return (
    <svg width={s} height={s} viewBox="0 0 48 48" className="lethe" aria-hidden="true">
      <circle cx="24" cy="24" r="22" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <circle cx="24" cy="24" r="17" fill="none" stroke="currentColor" strokeWidth="0.6" opacity="0.6" />
      <path d="M24 9 L24 39 M9 24 L39 24" stroke="currentColor" strokeWidth="0.6" opacity="0.45" />
      <path d="M12 24 Q24 12 36 24 Q24 36 12 24 Z" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <circle cx="24" cy="24" r="4" fill="currentColor" />
      <text x="24" y="47" textAnchor="middle" fontSize="6" fill="currentColor" opacity="0.7">IX</text>
    </svg>
  );
}

/** The Grays: faint drifting shapes that gather while agents are at work. */
function Grays({ live }: { live: boolean }) {
  return (
    <div className={`grays ${live ? "live" : ""}`} aria-hidden="true">
      {Array.from({ length: 7 }).map((_, i) => <span key={i} className={`g g${i}`} />)}
    </div>
  );
}

# Campus Customs Multi-Agent Operations: harness

This file describes the harness around the agent team: the data (§1), the MCP tools (§2, §4), the five agents (§3), the audit trail (§5), the safety rules and token limits (§6), the API routes (§7), the dashboard (§8) and the graded full run (§9).

**How the pieces connect:** React dashboard (`frontend/`, port 5173) → FastAPI routes (`backend/main.py`, port 8000) → the five PydanticAI agents on `gpt-6-luna` via Portkey (`backend/agents/`) → the Campus Customs MCP server (`mcp_server/`) → `data/campus_customs_new.db`. Every step is appended to `output/audit_trail.json`, and money only moves when a human approves on the dashboard.

## 1. Data: `data/campus_customs.db`

`data/campus_customs.db` is the original and stays untouched. Every agent, tool and the MCP server work on the copy, `data/campus_customs_new.db`, and we reset that copy from the original before a full run.

| Table | Fields | Why it matters for the agents |
|---|---|---|
| `desk` | `date_today`, `notes` | "Today" for the shop (2026-08-31); every agent uses it, never the computer clock, to decide what is due or overdue. |
| `tickets` | `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at` | The board of open work: the Boss reads each ticket, routes it by `type`, and follows `sku`/`lease_id`/`invoice_id` to the other tables. |
| `inventory` | `sku`, `name`, `size`, `qty`, `location` (key: `sku` + `size`) | Inventory checks stock by SKU and size and spots shortfalls against what a ticket asks for. |
| `pricing` | `sku`, `unit_cost`, `list_price` | Accounting uses it to check margins before agreeing to a discount and to price a restock purchase order. |
| `vendors` | `id`, `name`, `specialty`, `lead_days` | Inventory matches a vendor to the product by `specialty`; `lead_days` is the only source for restock lead times. |
| `invoices` | `id`, `vendor_id`, `amount`, `due_date`, `status`, `description` | Bills the shop owes; an open unpaid invoice blocks that vendor from shipping, so Inventory and Accounting must check it before ordering. |
| `leases` | `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes` | Facilities' table: what rent is owed for the shop space and when. |
| `cash_accounts` | `name`, `balance`, `date` | The cash available (checking, $3,400); the pay tool must refuse any payment that would push it below zero. |
| `payments` | `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by` | The record of money out; `approved_by` is required, so every payment carries the name of the human who approved it. Empty at the start. |

Two tables the MCP server adds to the **working copy only** (a reset removes them):

| Table | Fields | Why it matters for the agents |
|---|---|---|
| `payment_requests` | `id`, `ticket_id`, `kind`, `ref_id`, `payee`, `amount`, `sku`, `size`, `qty`, `reason`, `requested_by`, `status`, `created_at`, `decided_by`, `decided_at`, `decision_note`, `payment_id` | The human approval queue. Accounting files payments here (`pending`); only a person moves them to `paid` or `rejected`. |
| `board_drafts` | `id`, `ticket_id`, `author`, `recipient`, `subject`, `body`, `status`, `created_at` | "The board": Customer Service's messages wait here as `draft`; nothing is ever sent by an agent. |

### How the tables link

- `tickets.invoice_id` → `invoices.id` → `invoices.vendor_id` → `vendors.id`
- `tickets.lease_id` → `leases.id`
- `tickets.sku` + `tickets.size` → `inventory` (`sku`, `size`); `tickets.sku` → `pricing.sku`
- `payments.ref_id` points to an invoice or a lease, depending on `payments.kind` (not enforced by a foreign key).
- No table links a SKU to a vendor; the agent matches by `vendors.specialty`.

### The three open tickets

| Ticket | Type | Ask | Linked rows | What the agents must work out |
|---|---|---|---|---|
| 101 | `customer_order` | Tauhid Zaman, 1 Classic Bulldog Tee (`CC-TEE-WHITE`), size S | `inventory`: S has 0 in stock. `invoice_id` 501: Bulldog Print Co (vendor 1, apparel reprint, 5 lead days), $840, due 2026-08-28, `open`. | Out of stock. The reprint vendor won't ship while invoice 501 is unpaid, and it is 3 days overdue. Paying it needs human approval. |
| 102 | `rent_notice` | Elm City Properties, rent due | `lease_id` 1: Chapel Street shop, $2,400, next due 2026-09-02 | Rent is due in 2 days. Paying it needs human approval, then updates to `leases.next_due`, `cash_accounts` and `payments`. |
| 103 | `price_override` | Yale AI Club, 20 Basic Hoodie Big Yale (`CC-HOOD-NAVY`), size M, bulk discount | `inventory`: M has 8 in stock. `pricing`: cost $22, list $58. | A shortfall of 12, which needs a reprint from Bulldog Print Co (the same vendor blocked by invoice 501). The discount decision has to protect the margin. |

Cash check: $3,400 in checking. Paying invoice 501 ($840) and rent ($2,400) uses $3,240 and leaves $160, so any restock order on top of both would go negative.

## 2. Tools: the Campus Customs MCP server (`mcp_server/`)

Every agent uses these tools. They read `data/campus_customs_new.db` through a read-only connection, return only values in the database, and take "today" from `desk.date_today`.

### `check_stock(sku, size, qty_needed)`

- **Reads:** `inventory`
- **Unlocks:** ticket **103** (Yale AI Club, 20 × `CC-HOOD-NAVY` size M)
- **Why it is the right tool:** Ticket 103 asks for 20 size-M hoodies, and only this tool compares that quantity with the `inventory` row for `CC-HOOD-NAVY`/M, returning 8 on hand and a shortfall of 12. That tells the Boss a restock is needed before anyone talks about a bulk discount.

### `check_vendor_hold(vendor_id)`

- **Reads:** `vendors`, `invoices`, `desk`
- **Unlocks:** ticket **101** (Tauhid Zaman, 1 × `CC-TEE-WHITE` size S, linked to invoice 501)
- **Why it is the right tool:** Ticket 101's size-S tee is out of stock and only Bulldog Print Co (vendor 1) can reprint it, so this tool checks the shop rule that a vendor with an open unpaid invoice won't ship. It returns invoice 501 ($840, due 2026-08-28, 3 days past due as of 2026-08-31) and `can_ship: false`, which shows that the order is blocked by the unpaid bill, not just by missing stock.

### `get_rent_due(lease_id)`

- **Reads:** `leases`, `desk`, `cash_accounts`
- **Unlocks:** ticket **102** (Elm City Properties rent notice, `lease_id` 1)
- **Why it is the right tool:** Ticket 102 is a rent notice tied to lease 1, and this tool confirms from `leases` the $2,400 rent due 2026-09-02 (2 days from `desk.date_today`), then checks it against the $3,400 in `cash_accounts`. Facilities and Accounting can see the payment is covered, with $1,000 left, before asking a human to approve it, and the tool pays nothing itself.

## 3. Agents (`backend/`)

PydanticAI, every agent on `gpt-6-luna` through Portkey (`PORTKEY_API_KEY`). The model name appears once, in `backend/config.py`. Full connectivity: every agent has a `hand_off(to_agent, task)` tool and can delegate to any other agent.

| Agent | File / prompt / output type | Job | MCP tools it can call |
|---|---|---|---|
| **Boss** | `agents/boss.py`, `prompts/boss.md`, `BossDecision` | Reads each ticket, routes work, combines the reports, makes the final call and moves the ticket on the board | `get_ticket`, `list_open_tickets`, `get_today`, `get_cash_position`, `list_payment_requests`, `update_ticket_status` |
| **Inventory** | `agents/inventory.py`, `prompts/inventory.md`, `InventoryReport` | Checks stock by SKU and size, measures shortfalls, finds the restock vendor, reports lead time and vendor holds | `get_ticket`, `get_today`, `check_stock`, `list_vendors`, `check_vendor_hold` |
| **Accounting** | `agents/accounting.py`, `prompts/accounting.md`, `AccountingReport` | Watches cash and invoices, checks margins on discounts, files payments and purchase orders **for human approval** | `get_ticket`, `get_today`, `get_cash_position`, `get_invoice`, `get_rent_due`, `check_discount`, `check_vendor_hold`, `list_payment_requests`, `request_payment` |
| **Facilities** | `agents/facilities.py`, `prompts/facilities.md`, `FacilitiesReport` | Handles the shop space: lease, rent amount, due date, urgency | `get_ticket`, `get_today`, `get_rent_due`, `get_cash_position` |
| **Customer Service** | `agents/customer_service.py`, `prompts/customer_service.md`, `CustomerDraft` | Drafts customer messages from confirmed facts only and posts them to the board as drafts | `get_ticket`, `get_today`, `post_draft` |

Shared pieces: `agents/_base.py` (each agent's tool filter, the hand-off tool and the audited agent loop), `models.py` (data types), `config.py` (model, MCP connection, limits, tool allow-lists), `team.py` (runs a ticket: `python -m backend.team --ticket 101`), `audit.py` (audit trail), `approvals.py` (human approval desk), `reset_db.py` (restore the working copy before a full run).

## 4. MCP tools (`mcp_server/server.py`)

Every shop fact and shop action goes through the `campus-customs` MCP server over `data/campus_customs_new.db`; there is no second tool layer. Read tools use a read-only connection. Write tools do one narrow, rule-checked change, and amounts always come from the database, never from the agent.

| Tool | Tables | Type | Used by |
|---|---|---|---|
| `get_today` | `desk` | read | all |
| `list_tickets` | `tickets` | read | backend `GET /api/tickets` |
| `list_open_tickets` | `tickets` | read | Boss |
| `get_ticket` | `tickets` + linked `inventory`, `pricing`, `leases`, `invoices`, `vendors`, `board_drafts`, `payment_requests` | read | all |
| `check_stock` | `inventory` | read | Inventory |
| `list_vendors` | `vendors` | read | Inventory |
| `check_vendor_hold` | `vendors`, `invoices`, `desk` | read | Inventory, Accounting |
| `get_invoice` | `invoices`, `vendors`, `desk` | read | Accounting |
| `get_rent_due` | `leases`, `desk`, `cash_accounts` | read | Facilities, Accounting |
| `get_cash_position` | `cash_accounts`, `invoices`, `payment_requests`, `desk` | read | Boss, Accounting, Facilities |
| `check_discount` | `pricing` | read | Accounting |
| `list_payment_requests` | `payment_requests`, `payments` | read | Boss, Accounting |
| `request_payment` | reads `invoices`/`leases`/`pricing`/`vendors`/`inventory`/`cash_accounts`; writes `payment_requests` | write (no money moves) | Accounting |
| `post_draft` | writes `board_drafts` | write (draft only, never sent) | Customer Service |
| `update_ticket_status` | `tickets` (`status`, `notes`) | write | Boss |
| `approve_and_pay` | writes `payments`, `cash_accounts`, `invoices` or `leases`, `payment_requests` | write, **human only** | `backend/approvals.py` (a person), never an agent |
| `reject_payment` | writes `payment_requests` | write, **human only** | `backend/approvals.py` (a person), never an agent |

`payment_requests` and `board_drafts` are two small tables the server adds to the **working copy** only: the approval queue and "the board" for drafts. `reset_db.py` removes them, and `campus_customs.db` is never touched.

## 5. Audit trail (`output/audit_trail.json`)

Every agent writes to one JSON list that only grows. Each write appends and atomically replaces the file; nothing is ever wiped. Every record carries `ts`, `run_id`, `ticket_id`, `agent` and `chain` (who handed off to whom). Events:

- `run_start` / `run_end` / `run_failed`: one per ticket run, with limits and total tokens.
- `agent_start`: the task and the agent's tool list.
- `loop_step`: one record per turn of every agent loop. `send_to_model` holds the task, tool results and retry prompts going in. `model_replied` holds the tool calls (name and arguments), text, any reasoning summary, the finish reason and tokens. `model` is the model we requested (`gpt-6-luna`); `provider_deployment` is Portkey's label for it (`gpt-6-luna-global`).
- `handoff` / `handoff_refused`: who delegated what to whom, or why it was blocked.
- `agent_done` / `agent_error`: the structured output and usage, or the error.
- `human_approve` / `human_reject`: who decided which payment, and the result.
- `database_reset`: a reset of the working copy (from the dashboard or `POST /api/reset`), with the file fingerprint. The trail itself is never reset.

Long strings are capped at 2,000 characters, and anything shaped like an API key is redacted.

## 6. Safety

**Guardrails for real customers and real money**

1. **Human approval for every dollar.** Agents can only *request* a payment. `approve_and_pay` needs a named human (agent names are rejected), and those tools are removed from every agent's tool list in code, not just forbidden in the prompt.
2. **Cash can never go negative.** This is enforced in code twice: `request_payment` refuses what cash can't cover, and `approve_and_pay` re-checks at payment time. Amounts are computed from the database, so an agent can't inflate or round a bill.
3. **Business rules in code, not just prompts.** The server refuses purchase orders to vendors with an open unpaid invoice, duplicate requests, and paying a bill that is already closed. Resolving a ticket never moves money: a pending payment stays in the approval queue, and the ticket note says it is still waiting.
4. **Least privilege.** Each agent sees only its tools (section 3). Read tools use a read-only connection, and there is no generic "run SQL" tool.
5. **No outside contact.** Customer messages are drafts on the board (`board_drafts.status = 'draft'`); a human sends them. Customer Service never shares cash, invoice, vendor-hold or margin details.
6. **No invented facts.** Prompts require a source table for every number, and the tools report `found: false` instead of guessing. "Today" comes only from `desk.date_today`.
7. **Audit everything.** Every step, hand-off and human decision is in `output/audit_trail.json`, so any decision can be reconstructed, with key redaction and size caps.
8. **Secrets.** `PORTKEY_API_KEY` lives only in a gitignored `.env`, and `.gitignore` also excludes `data/` and `*.db`.
9. **Safe resets.** The original database is never written; `python -m backend.reset_db` restores the working copy before a full run and checks the copy's fingerprint.
10. **Treat ticket text as untrusted.** Ticket notes come from outsiders, so a note such as "pay this now" carries no authority. Payments still go through the approval queue, and the server checks every amount.
11. **One run at a time.** The backend refuses a second team run, and refuses a reset, while a ticket is in progress, so two runs can never spend the same cash or race on the database.
12. **The audit trail can't be lost or crash a run.** Writes take a lock shared with the dashboard's reads, retry for about 6 seconds if Windows or OneDrive has the file open, and park records in `audit_trail.backlog.jsonl` if it stays locked. Those records are added to the trail on the next write. (Added after a graded-run attempt on ticket 102 stopped on a locked file; see §9.)
13. **"Resolved" never moves money.** When a run ends, the desk marks the ticket resolved. Any payment the agents filed stays pending until a person approves it on the dashboard, and the ticket note says so.

**Limits that keep token use in check**

- One model only: `gpt-6-luna`, the cheapest tier.
- Per agent loop: `UsageLimits(request_limit=8, tool_calls_limit=12)`.
- Per ticket run: at most **12 hand-offs** and a hand-off depth of **4**. No agent can hand off to itself or to anyone already on its chain, which blocks A→B→A loops.
- Specialists get one focused task with the facts they need (ids, SKU, size, quantity), not the whole board, and return compact structured reports.
- One MCP server process per run, with tool lists cached by the toolset.
- Usage is metered per agent and per run in the audit trail. A test run of ticket 101 took 20 model calls, 58,378 input and 5,737 output tokens: about **$0.009** at $0.10 / $0.50 per 1M tokens.

## 7. Backend routes (`backend/main.py`, FastAPI)

Start from `backend/`: `uvicorn main:app --reload --port 8000` → `http://localhost:8000` (interactive docs at `/docs`). CORS allows the React dev server on any `localhost` / `127.0.0.1` port. Every route reads and writes through the MCP server, except reset, which is a whole-file copy.

- `GET /api/health`: server is up, the model in use, and which ticket (if any) the team is working.
- `GET /api/tickets`: the three tickets with their status and whether each is `open` or `resolved`.
- `POST /api/tickets/{ticket_id}/run`: run the agent team (Boss first) on that one ticket, and mark it `resolved` on the board when the run finishes. It returns at once with a `run_key` (send `{"wait": true}` to block until it finishes), and only one run at a time is allowed.
- `GET /api/runs/{run_key}`: status of a run started above (`running`, `done` or `failed`) and the Boss's final decision.
- `GET /api/events?limit=50&ticket_id=&run_id=`: recent agent events from `output/audit_trail.json`: what each agent said, which tools it used, and hand-offs, so the board can refresh.
- `GET /api/payments?status=pending`: payment and purchase requests the agents filed, waiting for a human.
- `POST /api/payments/{request_id}/approve` `{"approver": "Name"}`: a human approves a payment or purchase. **The only route that changes cash**; it is refused if cash would go negative or the bill is already closed.
- `POST /api/payments/{request_id}/reject` `{"approver": "Name", "note": ""}`: a human rejects a request. No money moves.
- `GET /api/cash`: current checking balance from `cash_accounts`, plus what would be left if every pending request were paid.
- `POST /api/reset`: copy `data/campus_customs.db` over `data/campus_customs_new.db` for a fresh run. The original is only read, the audit trail is kept, and reset is refused while a run is in progress.

**Evidence:** `output/route_check.json` records one call to each route on `http://localhost:8000` (2026-10-25): status codes, responses and the CORS header for `http://localhost:5173`. It covers running ticket 102, approving its rent payment ($3,400 → $1,000), a refused reject on the already-paid request, and a reset back to $3,400.

**Run note:** this project sits in OneDrive. While the server runs with `--reload`, OneDrive re-touching files in `backend/` as it syncs triggers a reload that stops a ticket run partway through. **Pause OneDrive syncing before a full run.**

## 8. Dashboard (`frontend/`, React + Vite + TypeScript)

Start it with `npm run dev` → `http://localhost:5173` (it calls `http://localhost:8000`, set by `VITE_API_URL`). The look and the reasons behind it are in `output/design.md`. What it does in the harness:

- **The Board** (`GET /api/tickets`): all three tickets with their status. A red wax seal marks a resolved ticket; "In session" marks the one running.
- **Start the agent team** (`POST /api/tickets/{id}/run`): one run at a time. The button locks while the team works.
- **Live agent activity** (`GET /api/events`, polled every second during a run): each agent's tool calls with arguments, the tool answers, hand-offs with the task passed on, and reports, in house colors. A meter shows model calls, tokens and estimated cost.
- **The Houses**: each agent's live status (idle, working, done) and what it is doing right now.
- **Summary** after a run: the Boss's decision, then one card per agent with what it concluded, its MCP tools and its hand-offs, plus any customer draft marked "not sent".
- **The Vault** (`GET /api/cash`): the checking balance, the balance if every pending request were paid, and a bar against the opening $3,400.
- **Awaiting your seal** (`GET /api/payments`, `POST /api/payments/{id}/approve` and `/reject`): every payment the agents filed, with the checking balance after paying it. A person types their name and clicks Approve & pay; the balance drops on screen.
- **Reset shop** (`POST /api/reset`): asks first, keeps the audit trail, and is disabled during a run.
- `?ticket=101` in the URL opens the desk on that ticket (used for `output/resolved_board.html`).

## 9. Graded full run (Problem 9)

On 2026-10-25 the working database was reset (13:58:50 EDT; checking **$3,400.00**). A `full_run_start` marker was added to the audit trail, and the three tickets were run from the dashboard. Records before the marker are build and test runs, kept because the trail is append-only.

| Ticket | Run | Agents (hand-offs) | Boss decision | Payment filed → human decision | Checking after |
|---|---|---|---|---|---|
| 101 | `150636c3cd58` · 19 calls · ≈ $0.0081 | Boss → Inventory, Accounting, Customer Service; Customer Service → Inventory (4) | Pay, pending approval | #1 invoice 501, $840 → approved by Natty G | $2,560.00 |
| 102 | `fed2e4e6e84a` · 11 calls · ≈ $0.0046 | Boss → Facilities, Accounting (2) | Pay, pending approval | #2 rent lease 1, $2,400 → approved by Natty G | $160.00 |
| 103 | `7f9f5b7f28b2` · 26 calls · ≈ $0.0129 | Boss → Inventory, Accounting, Customer Service; Customer Service → Inventory, Accounting (5); Accounting → Boss blocked by the loop guard | Escalated to a human | none (vendor on hold; a $264 restock wouldn't fit the $160 left) | $160.00 |

- **Ending checking $160.00**, which matches `cash_accounts` (3,400 − 840 − 2,400). The `payments` table has two rows, both `approved_by = 'Natty G'`.
- **All three tickets are `resolved`**, with drafts #1 (Tauhid Zaman) and #2 (Yale AI Club) on the board, not sent.
- **One failed attempt:** ticket 102's first attempt (`517893a9e532`, 14:06 EDT) stopped after 5 seconds, before changing anything, when Windows refused to replace a locked `audit_trail.json`. It is logged as `run_failed`, the writer was fixed (§6, rule 12), and 102 was re-run.
- **Whole graded run:** 56 model calls, 167,387 input and 17,656 output tokens, **≈ $0.026** at gpt-6-luna prices.
- **Evidence:** `output/desk_tickets.html` (Expected vs. Actual per ticket, plus the Cash tab), `output/resolved_tickets.json`, `output/resolved_board.html` (dashboard screenshots for 101, 102 and 103), and `output/audit_trail.json` (172 records after the marker).

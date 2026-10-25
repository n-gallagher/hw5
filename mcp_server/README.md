# Campus Customs MCP server

**What it is for.** This is the shared tool layer for the Campus Customs multi-agent team. Every agent (Boss, Inventory, Accounting, Facilities, Customer Service) gets shop facts and takes shop actions only through these tools, so they all work from the same database under the same rules. It is built with FastMCP: each tool is a Python function marked `@mcp.tool`, and its docstring is the manual the agent reads.

**Database.** `data/campus_customs_new.db`, the working copy of the original `data/campus_customs.db`. The original is never touched; reset the working copy with `python -m backend.reset_db`.

- Read tools open the database **read-only** (`mode=ro`) and return only values in the database; a missing row comes back as `found: false`, never a guess.
- Write tools make one narrow change each, with the shop rules checked in code. Amounts are always computed from the database, never taken from the caller.
- "Today" is always `desk.date_today`.
- The server adds two tables to the working copy only: `payment_requests` (the approval queue) and `board_drafts` (customer drafts on the board).

## Tools (17)

**Read**

| Tool | Reads | What it returns |
|---|---|---|
| `get_today()` | `desk` | the shop's date and desk notes |
| `list_tickets()` | `tickets` | every ticket, open or resolved, with its status (the dashboard board) |
| `list_open_tickets()` | `tickets` | every ticket not yet resolved |
| `get_ticket(ticket_id)` | `tickets` + linked `inventory`, `pricing`, `leases`, `invoices`, `vendors`, drafts, payment requests | one ticket and everything it links to |
| `check_stock(sku, size, qty_needed)` | `inventory` | `on_hand`, `shortfall`, `can_fill` (ticket 103) |
| `list_vendors(specialty_contains)` | `vendors` | vendors by specialty, with `lead_days` |
| `check_vendor_hold(vendor_id)` | `vendors`, `invoices`, `desk` | open invoices, days past due, `can_ship` (ticket 101) |
| `get_invoice(invoice_id)` | `invoices`, `vendors`, `desk` | one invoice, its vendor, days past due |
| `get_rent_due(lease_id)` | `leases`, `desk`, `cash_accounts` | rent, due date, days until due, whether cash covers it (ticket 102) |
| `get_cash_position()` | `cash_accounts`, `invoices`, `payment_requests` | cash, open bills, pending requests, cash left if all are paid |
| `check_discount(sku, qty, discount_pct)` | `pricing` | discounted price, margin, `below_cost`, largest discount at cost |
| `list_payment_requests(status)` | `payment_requests`, `payments` | the approval queue and the payments log |

**Write (agents)**

| Tool | Writes | Rules enforced |
|---|---|---|
| `request_payment(kind, ...)` | `payment_requests` | files an invoice, rent or purchase-order payment **for human approval** and moves no money; refuses closed bills, duplicates, vendors on hold, and amounts cash can't cover |
| `post_draft(ticket_id, ...)` | `board_drafts` | posts a customer message as a **draft**; nothing is ever sent |
| `update_ticket_status(ticket_id, status, note, updated_by)` | `tickets` | adds a dated note; resolving never moves money, and any payment still pending is noted and stays in the approval queue |

**Write (humans only; the backend never gives these to an agent)**

| Tool | Writes | Rules enforced |
|---|---|---|
| `approve_and_pay(request_id, approver)` | `payments`, `cash_accounts`, `invoices` / `leases`, `payment_requests` | needs a named human; refuses if cash would go negative or the bill is no longer open; marks the invoice paid or moves the lease's `next_due` forward one month |
| `reject_payment(request_id, approver, note)` | `payment_requests` | needs a named human; no money moves |

People use these through `python -m backend.approvals list | approve ID --by "Name" | reject ID --by "Name"`.

## Run

```bash
cd mcp_server
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python server.py
```

It runs over stdio: the vibe coder (via `.mcp.json` at the project root) or the backend (via PydanticAI's `MCPToolset`) launches this file and talks to it through the terminal pipes.

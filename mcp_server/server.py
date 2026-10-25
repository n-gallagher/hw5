"""Campus Customs MCP server.

Every agent on the Campus Customs team gets shop facts and takes shop actions
only through these tools, over data/campus_customs_new.db (the working copy;
data/campus_customs.db is never touched).

- Read tools open the database read-only (mode=ro): they cannot change a table.
- Write tools are narrow and rule-checked in code: an agent can REQUEST a
  payment, post a DRAFT to the board, or move a ticket's status. Money only
  moves in approve_and_pay, which needs a named human approver and refuses
  any payment that would push cash below zero. The backend hides the
  human-only tools (approve_and_pay, reject_payment) from every agent.
- Amounts are always computed from the database, never taken from the caller.
- "Today" is desk.date_today, never the computer clock.

Run over stdio:  python mcp_server/server.py
"""

from __future__ import annotations

import calendar
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

# CAMPUS_CUSTOMS_DB overrides the path for tests on a scratch copy only.
DB_PATH = Path(os.environ.get("CAMPUS_CUSTOMS_DB")
               or Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db")

mcp = FastMCP("campus-customs")

TICKET_STATUSES = ("open", "in_progress", "awaiting_approval", "resolved", "escalated")
HUMAN_ONLY_TOOLS = ("approve_and_pay", "reject_payment")

# Two small tables the agents need that the original schema doesn't have.
# They live only in the working copy and disappear on a reset.
_EXTRA_TABLES = """
CREATE TABLE IF NOT EXISTS payment_requests (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER,
    kind TEXT NOT NULL,              -- invoice | rent | purchase_order
    ref_id INTEGER,                  -- invoice id, lease id, or vendor id (purchase_order)
    payee TEXT NOT NULL,
    amount REAL NOT NULL,
    sku TEXT, size TEXT, qty INTEGER,  -- purchase orders only
    reason TEXT NOT NULL,
    requested_by TEXT NOT NULL,      -- the agent that asked
    status TEXT NOT NULL,            -- pending | paid | rejected
    created_at TEXT NOT NULL,
    decided_by TEXT,                 -- the human who approved or rejected
    decided_at TEXT,
    decision_note TEXT,
    payment_id INTEGER
);
CREATE TABLE IF NOT EXISTS board_drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    author TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',  -- drafts are never sent by an agent
    created_at TEXT NOT NULL
);
"""


# ---------------------------------------------------------------- helpers

def _check_db() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}")


def _ro() -> sqlite3.Connection:
    """Read-only connection: any write through it fails."""
    _check_db()
    conn = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _rw():
    """Read-write connection for the narrow write tools; one transaction per call."""
    _check_db()
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_EXTRA_TABLES)
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _today(conn: sqlite3.Connection) -> str:
    return conn.execute("SELECT date_today FROM desk").fetchone()["date_today"]


def _days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _add_month(iso: str) -> str:
    d = date.fromisoformat(iso)
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1])).isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row(r: sqlite3.Row | None) -> dict | None:
    return dict(r) if r is not None else None


def _cash(conn: sqlite3.Connection) -> float:
    return sum(r["balance"] for r in conn.execute("SELECT balance FROM cash_accounts"))


def _pending_total(conn: sqlite3.Connection) -> float:
    if not _has_table(conn, "payment_requests"):
        return 0.0
    r = conn.execute("SELECT COALESCE(SUM(amount),0) AS t FROM payment_requests WHERE status='pending'").fetchone()
    return r["t"]


def _vendor_hold(conn: sqlite3.Connection, vendor_id: int, today: str) -> dict:
    vendor = conn.execute(
        "SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?", (vendor_id,)
    ).fetchone()
    if vendor is None:
        return {"found": False, "vendor_id": vendor_id, "message": "No vendor with this id."}
    invoices = conn.execute(
        "SELECT id, amount, due_date, status, description FROM invoices "
        "WHERE vendor_id = ? AND status = 'open' ORDER BY due_date", (vendor_id,),
    ).fetchall()
    open_invoices = []
    for inv in invoices:
        late = _days_between(inv["due_date"], today)
        open_invoices.append({
            "invoice_id": inv["id"], "amount": inv["amount"], "due_date": inv["due_date"],
            "status": inv["status"], "description": inv["description"],
            "days_past_due": max(0, late), "overdue": late > 0,
        })
    can_ship = not open_invoices
    return {
        "found": True, "today": today, "vendor_id": vendor["id"], "vendor_name": vendor["name"],
        "specialty": vendor["specialty"], "lead_days": vendor["lead_days"],
        "open_invoices": open_invoices,
        "open_invoice_total": sum(i["amount"] for i in open_invoices),
        "can_ship": can_ship,
        "reason": ("No open invoices; vendor can ship." if can_ship
                   else "Vendor will not ship while it has an open unpaid invoice."),
        "source": "vendors, invoices, desk",
    }


# ======================================================= read tools (all agents)

@mcp.tool
def get_today() -> dict:
    """Return the shop's 'today' (desk.date_today) and any desk notes. Use this date for due/overdue math."""
    with _ro() as conn:
        row = conn.execute("SELECT date_today, notes FROM desk").fetchone()
    return {"date_today": row["date_today"], "notes": row["notes"], "source": "desk"}


@mcp.tool
def list_open_tickets() -> dict:
    """List every ticket on the board that is not resolved, oldest first (tickets table)."""
    with _ro() as conn:
        rows = conn.execute(
            "SELECT id, type, requester, subject, status, created_at FROM tickets "
            "WHERE status != 'resolved' ORDER BY created_at"
        ).fetchall()
    return {"tickets": [dict(r) for r in rows], "count": len(rows), "source": "tickets"}


@mcp.tool
def list_tickets() -> dict:
    """List every ticket on the board, open or resolved, with its status (tickets table)."""
    with _ro() as conn:
        rows = conn.execute(
            "SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at "
            "FROM tickets ORDER BY id"
        ).fetchall()
    return {"tickets": [dict(r) for r in rows], "count": len(rows), "source": "tickets"}


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Read one ticket and follow its links: the inventory and pricing rows for its
    SKU/size, its lease, its invoice (with the vendor), any drafts and payment
    requests already filed for it. Start every ticket with this."""
    with _ro() as conn:
        t = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if t is None:
            return {"found": False, "ticket_id": ticket_id, "message": "No ticket with this id."}
        out: dict = {"found": True, "today": _today(conn), "ticket": dict(t), "links": {}}
        links = out["links"]
        if t["sku"]:
            links["inventory"] = _row(conn.execute(
                "SELECT * FROM inventory WHERE sku = ? AND size = ?", (t["sku"], t["size"])).fetchone())
            links["pricing"] = _row(conn.execute(
                "SELECT * FROM pricing WHERE sku = ?", (t["sku"],)).fetchone())
        if t["lease_id"] is not None:
            links["lease"] = _row(conn.execute(
                "SELECT * FROM leases WHERE id = ?", (t["lease_id"],)).fetchone())
        if t["invoice_id"] is not None:
            inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (t["invoice_id"],)).fetchone()
            links["invoice"] = _row(inv)
            if inv is not None:
                links["invoice_vendor"] = _row(conn.execute(
                    "SELECT * FROM vendors WHERE id = ?", (inv["vendor_id"],)).fetchone())
        if _has_table(conn, "board_drafts"):
            links["drafts"] = [dict(r) for r in conn.execute(
                "SELECT id, author, recipient, subject, status, created_at FROM board_drafts WHERE ticket_id = ?",
                (ticket_id,))]
        if _has_table(conn, "payment_requests"):
            links["payment_requests"] = [dict(r) for r in conn.execute(
                "SELECT id, kind, ref_id, payee, amount, status, requested_by, decided_by "
                "FROM payment_requests WHERE ticket_id = ?", (ticket_id,))]
    out["source"] = "tickets + linked inventory, pricing, leases, invoices, vendors"
    return out


@mcp.tool
def check_stock(sku: str, size: str, qty_needed: int) -> dict:
    """Check how many units of one SKU and size are on hand and how many are short.

    Reads the inventory table. Use it before promising a customer order or bulk
    request. Returns on_hand, qty_needed, shortfall (0 if there is enough) and
    can_fill. Returns found=False if the SKU/size is not in inventory.
    """
    if qty_needed < 1:
        return {"found": False, "error": "qty_needed must be at least 1"}
    with _ro() as conn:
        row = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku.strip(), size.strip()),
        ).fetchone()
    if row is None:
        return {"found": False, "sku": sku, "size": size,
                "message": "No inventory row for this SKU and size."}
    on_hand = row["qty"]
    shortfall = max(0, qty_needed - on_hand)
    return {
        "found": True, "sku": row["sku"], "name": row["name"], "size": row["size"],
        "location": row["location"], "on_hand": on_hand, "qty_needed": qty_needed,
        "shortfall": shortfall, "can_fill": shortfall == 0, "source": "inventory",
    }


@mcp.tool
def list_vendors(specialty_contains: str | None = None) -> dict:
    """List vendors (id, name, specialty, lead_days), optionally filtered by a word in
    their specialty, e.g. 'apparel' or 'mugs'. No table links SKUs to vendors, so
    use this to match a product to the vendor whose specialty fits."""
    with _ro() as conn:
        if specialty_contains:
            rows = conn.execute(
                "SELECT id, name, specialty, lead_days FROM vendors WHERE specialty LIKE ? ORDER BY id",
                (f"%{specialty_contains.strip()}%",)).fetchall()
        else:
            rows = conn.execute("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id").fetchall()
    return {"vendors": [dict(r) for r in rows], "count": len(rows), "source": "vendors"}


@mcp.tool
def check_vendor_hold(vendor_id: int) -> dict:
    """Check whether a vendor will ship, based on its open unpaid invoices.

    Shop rule: a vendor will not ship new product while it has an open unpaid
    invoice. Reads vendors (name, specialty, lead_days), invoices (status
    'open') and desk.date_today to work out how many days each invoice is past
    due. Returns can_ship=False and the blocking invoices if any are open.
    """
    with _ro() as conn:
        return _vendor_hold(conn, vendor_id, _today(conn))


@mcp.tool
def get_invoice(invoice_id: int) -> dict:
    """Read one invoice with its vendor and how many days past due it is (invoices, vendors, desk)."""
    with _ro() as conn:
        today = _today(conn)
        inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if inv is None:
            return {"found": False, "invoice_id": invoice_id, "message": "No invoice with this id."}
        vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (inv["vendor_id"],)).fetchone()
    late = _days_between(inv["due_date"], today)
    return {
        "found": True, "today": today, "invoice": dict(inv), "vendor": _row(vendor),
        "days_past_due": max(0, late), "overdue": inv["status"] == "open" and late > 0,
        "source": "invoices, vendors, desk",
    }


@mcp.tool
def get_rent_due(lease_id: int) -> dict:
    """Look up the rent due on one lease and whether cash covers it. Read-only: pays nothing.

    Reads leases (landlord, monthly_rent, next_due), desk.date_today for days
    until due, and cash_accounts for the balance. Returns cash_covers_rent and
    the balance that would be left after paying. Paying rent is a separate step
    that needs human approval.
    """
    with _ro() as conn:
        today = _today(conn)
        lease = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        if lease is None:
            return {"found": False, "lease_id": lease_id, "message": "No lease with this id."}
        accounts = conn.execute("SELECT name, balance, date FROM cash_accounts ORDER BY name").fetchall()
    cash_total = sum(a["balance"] for a in accounts)
    rent = lease["monthly_rent"]
    days_until_due = _days_between(today, lease["next_due"])
    return {
        "found": True, "today": today, "lease_id": lease["id"], "space_name": lease["space_name"],
        "landlord": lease["landlord"], "monthly_rent": rent, "next_due": lease["next_due"],
        "days_until_due": days_until_due, "overdue": days_until_due < 0,
        "cash_accounts": [{"name": a["name"], "balance": a["balance"], "as_of": a["date"]} for a in accounts],
        "cash_total": cash_total, "cash_covers_rent": cash_total >= rent,
        "cash_left_after_rent": cash_total - rent, "source": "leases, desk, cash_accounts",
    }


@mcp.tool
def get_cash_position() -> dict:
    """Cash on hand (cash_accounts), every open invoice, and payment requests still
    waiting for a human. Shows what cash would be left if everything pending were paid."""
    with _ro() as conn:
        today = _today(conn)
        accounts = [dict(r) for r in conn.execute("SELECT name, balance, date FROM cash_accounts")]
        open_inv = [dict(r) for r in conn.execute(
            "SELECT id, vendor_id, amount, due_date, description FROM invoices WHERE status='open' ORDER BY due_date")]
        pending = []
        if _has_table(conn, "payment_requests"):
            pending = [dict(r) for r in conn.execute(
                "SELECT id, ticket_id, kind, ref_id, payee, amount FROM payment_requests WHERE status='pending'")]
    cash = sum(a["balance"] for a in accounts)
    pending_total = sum(p["amount"] for p in pending)
    return {
        "today": today, "cash_accounts": accounts, "cash_total": cash,
        "open_invoices": open_inv, "open_invoice_total": sum(i["amount"] for i in open_inv),
        "pending_payment_requests": pending, "pending_total": pending_total,
        "cash_left_if_all_pending_paid": cash - pending_total,
        "source": "cash_accounts, invoices, payment_requests, desk",
    }


@mcp.tool
def check_discount(sku: str, qty: int, discount_pct: float) -> dict:
    """Price a discount from the pricing table: list price, unit cost, discounted price,
    margin per unit and in total, margin %, and the largest discount that still
    sells at or above cost. Flags any discount that sells below unit cost.
    discount_pct is a percent, e.g. 15 for 15% off. Use 0 to see full-price margin."""
    if qty < 1 or not 0 <= discount_pct < 100:
        return {"found": False, "error": "qty must be >= 1 and discount_pct between 0 and 100"}
    with _ro() as conn:
        p = conn.execute("SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (sku.strip(),)).fetchone()
    if p is None:
        return {"found": False, "sku": sku, "message": "No pricing row for this SKU."}
    cost, price = p["unit_cost"], p["list_price"]
    disc_price = round(price * (1 - discount_pct / 100), 2)
    unit_margin = round(disc_price - cost, 2)
    return {
        "found": True, "sku": p["sku"], "qty": qty, "unit_cost": cost, "list_price": price,
        "discount_pct": discount_pct, "discounted_price": disc_price,
        "margin_per_unit": unit_margin, "margin_pct": round(unit_margin / disc_price * 100, 1) if disc_price else None,
        "list_margin_pct": round((price - cost) / price * 100, 1),
        "revenue_total": round(disc_price * qty, 2), "cost_total": round(cost * qty, 2),
        "margin_total": round(unit_margin * qty, 2),
        "below_cost": disc_price < cost,
        "max_discount_pct_at_cost": round((1 - cost / price) * 100, 1),
        "source": "pricing",
    }


@mcp.tool
def list_payment_requests(status: Literal["pending", "paid", "rejected", "all"] = "pending") -> dict:
    """List payment requests and their human decisions (payment_requests), plus the payments log (payments)."""
    with _ro() as conn:
        reqs = []
        if _has_table(conn, "payment_requests"):
            q = "SELECT * FROM payment_requests" + ("" if status == "all" else " WHERE status = ?")
            reqs = [dict(r) for r in conn.execute(q, () if status == "all" else (status,))]
        payments = [dict(r) for r in conn.execute("SELECT * FROM payments ORDER BY id")]
    return {"payment_requests": reqs, "payments": payments, "source": "payment_requests, payments"}


# =================================================== write tools (agents)

@mcp.tool
def request_payment(
    kind: Literal["invoice", "rent", "purchase_order"],
    requested_by: str,
    reason: str,
    ticket_id: int | None = None,
    invoice_id: int | None = None,
    lease_id: int | None = None,
    vendor_id: int | None = None,
    sku: str | None = None,
    size: str | None = None,
    qty: int | None = None,
) -> dict:
    """File a payment for HUMAN approval. This never moves money.

    kind='invoice' needs invoice_id; kind='rent' needs lease_id; kind='purchase_order'
    needs vendor_id, sku, size and qty. The amount is computed from the database
    (invoice amount, lease monthly_rent, or qty x pricing.unit_cost), never taken
    from you. Refused if the bill is not open, a request for it is already
    pending, a purchase-order vendor is on hold, or cash on hand can't cover it.
    """
    with _rw() as conn:
        today = _today(conn)
        cash = _cash(conn)
        if kind == "invoice":
            if invoice_id is None:
                return {"filed": False, "refused": "invoice_id is required for kind='invoice'."}
            inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            if inv is None:
                return {"filed": False, "refused": f"No invoice {invoice_id}."}
            if inv["status"] != "open":
                return {"filed": False, "refused": f"Invoice {invoice_id} is '{inv['status']}', not open."}
            vendor = conn.execute("SELECT name FROM vendors WHERE id = ?", (inv["vendor_id"],)).fetchone()
            ref_id, payee, amount = invoice_id, vendor["name"], inv["amount"]
        elif kind == "rent":
            if lease_id is None:
                return {"filed": False, "refused": "lease_id is required for kind='rent'."}
            lease = conn.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone()
            if lease is None:
                return {"filed": False, "refused": f"No lease {lease_id}."}
            ref_id, payee, amount = lease_id, lease["landlord"], lease["monthly_rent"]
        else:  # purchase_order
            if None in (vendor_id, sku, size, qty) or (qty or 0) < 1:
                return {"filed": False, "refused": "vendor_id, sku, size and qty (>=1) are required for a purchase order."}
            hold = _vendor_hold(conn, vendor_id, today)
            if not hold.get("found"):
                return {"filed": False, "refused": f"No vendor {vendor_id}."}
            if not hold["can_ship"]:
                return {"filed": False, "refused": "Vendor is on hold (open unpaid invoice); it will not ship.",
                        "open_invoices": hold["open_invoices"]}
            p = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
            if p is None:
                return {"filed": False, "refused": f"No pricing for {sku}; can't cost the order."}
            if conn.execute("SELECT 1 FROM inventory WHERE sku=? AND size=?", (sku, size)).fetchone() is None:
                return {"filed": False, "refused": f"{sku} size {size} is not a stocked item."}
            ref_id, payee, amount = vendor_id, hold["vendor_name"], round(qty * p["unit_cost"], 2)

        dup = conn.execute(
            "SELECT id FROM payment_requests WHERE kind=? AND ref_id=? AND status='pending'"
            + (" AND sku=? AND size=?" if kind == "purchase_order" else ""),
            (kind, ref_id, sku, size) if kind == "purchase_order" else (kind, ref_id),
        ).fetchone()
        if dup:
            return {"filed": False, "refused": f"Request {dup['id']} for this is already pending human approval."}
        if amount > cash:
            return {"filed": False, "refused": f"Cash on hand ${cash:,.2f} can't cover ${amount:,.2f}; cash can never go negative.",
                    "cash_total": cash, "amount": amount}

        pending_before = _pending_total(conn)
        cur = conn.execute(
            "INSERT INTO payment_requests (ticket_id, kind, ref_id, payee, amount, sku, size, qty, reason, "
            "requested_by, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?, 'pending', ?)",
            (ticket_id, kind, ref_id, payee, amount, sku, size, qty, reason, requested_by, _now()),
        )
        pending_after = pending_before + amount
    return {
        "filed": True, "request_id": cur.lastrowid, "status": "pending",
        "message": "Waiting for a human to approve. No money has moved.",
        "kind": kind, "ref_id": ref_id, "payee": payee, "amount": amount,
        "cash_total": cash, "pending_total_including_this": pending_after,
        "cash_left_if_all_pending_paid": cash - pending_after,
        "warning": ("Pending requests together exceed cash; a human will have to choose."
                    if pending_after > cash else None),
        "source": "invoices/leases/pricing/vendors, cash_accounts, payment_requests",
    }


@mcp.tool
def post_draft(ticket_id: int, author: str, recipient: str, subject: str, body: str) -> dict:
    """Post a customer/requester message to the board as a DRAFT. Nothing is sent;
    a human reviews and sends it. Writes board_drafts."""
    if not body.strip() or not subject.strip():
        return {"posted": False, "refused": "subject and body are required."}
    with _rw() as conn:
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return {"posted": False, "refused": f"No ticket {ticket_id}."}
        cur = conn.execute(
            "INSERT INTO board_drafts (ticket_id, author, recipient, subject, body, status, created_at) "
            "VALUES (?,?,?,?,?, 'draft', ?)", (ticket_id, author, recipient, subject, body, _now()))
    return {"posted": True, "draft_id": cur.lastrowid, "status": "draft",
            "message": "Draft is on the board. It has NOT been sent.", "source": "board_drafts"}


@mcp.tool
def update_ticket_status(
    ticket_id: int,
    status: Literal["in_progress", "awaiting_approval", "resolved", "escalated"],
    note: str,
    updated_by: str,
) -> dict:
    """Move a ticket on the board and add a dated note (tickets.status, tickets.notes).
    Resolving a ticket never moves money: any payment request still pending stays in
    the human approval queue, and the note records that it is still waiting."""
    with _rw() as conn:
        t = conn.execute("SELECT status, notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if t is None:
            return {"updated": False, "refused": f"No ticket {ticket_id}."}
        pend = conn.execute(
            "SELECT COUNT(*) AS n FROM payment_requests WHERE ticket_id=? AND status='pending'", (ticket_id,)
        ).fetchone()["n"]
        if status == "resolved" and pend:
            note += f" ({pend} payment request(s) still awaiting human approval.)"
        today = _today(conn)
        new_notes = (t["notes"] or "") + f"\n[{today} {updated_by}] {t['status']} -> {status}: {note}"
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, new_notes.strip(), ticket_id))
    return {"updated": True, "ticket_id": ticket_id, "old_status": t["status"], "new_status": status,
            "pending_payment_requests": pend, "source": "tickets"}


# ============================== human-only tools (hidden from every agent)

@mcp.tool
def approve_and_pay(request_id: int, approver: str) -> dict:
    """HUMAN ONLY. Approve a pending payment request and pay it.

    Refuses if the request isn't pending, the approver is blank or an agent
    name, the bill is no longer open, or cash would go negative. On success it
    writes a payments row (approved_by = approver), lowers cash_accounts, and
    marks the invoice paid or moves the lease's next_due forward one month.
    """
    approver = (approver or "").strip()
    agent_names = {"boss", "inventory", "accounting", "facilities", "customer_service", "customer service"}
    if not approver or approver.lower() in agent_names:
        return {"paid": False, "refused": "A named human approver is required."}
    with _rw() as conn:
        today = _today(conn)
        req = conn.execute("SELECT * FROM payment_requests WHERE id = ?", (request_id,)).fetchone()
        if req is None:
            return {"paid": False, "refused": f"No payment request {request_id}."}
        if req["status"] != "pending":
            return {"paid": False, "refused": f"Request {request_id} is '{req['status']}', not pending."}
        account = conn.execute("SELECT name, balance FROM cash_accounts ORDER BY balance DESC").fetchone()
        if account is None or account["balance"] < req["amount"]:
            bal = account["balance"] if account else 0
            return {"paid": False, "refused": f"Not enough cash: ${bal:,.2f} on hand, ${req['amount']:,.2f} needed. Cash can never go negative."}

        if req["kind"] == "invoice":
            inv = conn.execute("SELECT status FROM invoices WHERE id = ?", (req["ref_id"],)).fetchone()
            if inv is None or inv["status"] != "open":
                return {"paid": False, "refused": f"Invoice {req['ref_id']} is no longer open."}
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
            effect = {"invoice_id": req["ref_id"], "invoice_status": "paid"}
        elif req["kind"] == "rent":
            lease = conn.execute("SELECT next_due FROM leases WHERE id = ?", (req["ref_id"],)).fetchone()
            new_due = _add_month(lease["next_due"])
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (new_due, req["ref_id"]))
            effect = {"lease_id": req["ref_id"], "old_next_due": lease["next_due"], "new_next_due": new_due}
        else:
            hold = _vendor_hold(conn, req["ref_id"], today)
            if not hold["can_ship"]:
                return {"paid": False, "refused": "Vendor is on hold (open unpaid invoice); pay that first."}
            effect = {"purchase_order": {"vendor_id": req["ref_id"], "sku": req["sku"], "size": req["size"],
                                         "qty": req["qty"], "arrives_in_days": hold["lead_days"]}}

        new_balance = account["balance"] - req["amount"]
        conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
                     (new_balance, today, account["name"]))
        pay = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?,?,?,?,?,?)",
            (req["kind"], req["ref_id"], req["amount"], account["name"], today, approver))
        conn.execute(
            "UPDATE payment_requests SET status='paid', decided_by=?, decided_at=?, payment_id=? WHERE id=?",
            (approver, _now(), pay.lastrowid, request_id))
    return {"paid": True, "request_id": request_id, "payment_id": pay.lastrowid, "amount": req["amount"],
            "payee": req["payee"], "approved_by": approver, "account": account["name"],
            "cash_before": account["balance"], "cash_after": new_balance, "effect": effect,
            "source": "payments, cash_accounts, invoices/leases, payment_requests"}


@mcp.tool
def reject_payment(request_id: int, approver: str, note: str) -> dict:
    """HUMAN ONLY. Reject a pending payment request. No money moves."""
    approver = (approver or "").strip()
    if not approver:
        return {"rejected": False, "refused": "A named human approver is required."}
    with _rw() as conn:
        req = conn.execute("SELECT status FROM payment_requests WHERE id = ?", (request_id,)).fetchone()
        if req is None or req["status"] != "pending":
            return {"rejected": False, "refused": f"Request {request_id} is not pending."}
        conn.execute(
            "UPDATE payment_requests SET status='rejected', decided_by=?, decided_at=?, decision_note=? WHERE id=?",
            (approver, _now(), note, request_id))
    return {"rejected": True, "request_id": request_id, "decided_by": approver, "source": "payment_requests"}


if __name__ == "__main__":
    mcp.run(show_banner=False)

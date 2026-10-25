# HW5: Campus Customs Multi-Agent Operations

An agent team that runs the Campus Customs shop. Open tickets (customer orders, rent, discount requests) land on a board. Five PydanticAI agents (**Boss, Inventory, Accounting, Facilities, Customer Service**) work them through a shared **MCP server**, a **FastAPI backend** runs the team, and a **React dashboard** ("The Lethe Desk") lets a person watch the agents live and approve any payment. Every agent uses **`gpt-6-luna` through Portkey**, and nothing else.

```
React board (frontend/, :5173) → FastAPI (backend/main.py, :8000) → 5 agents (backend/agents/)
      → Campus Customs MCP server (mcp_server/server.py) → data/campus_customs_new.db
```

## Layout

| Path | What it is |
|---|---|
| `data/campus_customs.db` | the **original** shop database (never written to) |
| `data/campus_customs_new.db` | the **working copy** every tool reads and writes (committed in its state after the graded run) |
| `mcp_server/` | `server.py` (17 FastMCP tools) and `README.md` |
| `backend/` | `main.py` (API routes), `models.py` (data types), `prompts/` (one prompt per agent), `agents/` (one file per role), `config.py` (model, MCP connection, limits), `team.py`, `audit.py`, `approvals.py`, `reset_db.py` |
| `frontend/` | React + Vite + TypeScript dashboard |
| `output/` | `harness.md`, `mcp_smoke.json`, `desk_tickets.html`, `design.md`, `resolved_tickets.json`, `resolved_board.html`, `audit_trail.json`, `route_check.json`, `github_url.txt` |
| `AI_prompts.md` | the log of what I asked my vibe coder, problem by problem |
| `.mcp.json` | connects the MCP server to a vibe coder (Claude Code) in this project |

## 1. Set up (once)

You need Python 3.12+ and Node 20+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # Windows: copy .env.example .env
# then edit .env and set PORTKEY_API_KEY=<your Portkey key>
```

`.env` is gitignored; only `.env.example` (key name, no value) is in the repo. The backend also looks for `.env` one folder up.

## 2. Copy the original database over the working copy (clean run)

The tools change `data/campus_customs_new.db` as tickets get resolved. To start clean, copy the untouched original over it, using either of these:

```bash
python -m backend.reset_db
```

```bash
cp data/campus_customs.db data/campus_customs_new.db    # Windows: copy data\campus_customs.db data\campus_customs_new.db
```

`reset_db` also checks that the copy matches the original byte for byte. After a reset, checking is $3,400.00 and tickets 101, 102 and 103 are open.

## 3. Start the MCP server

```bash
python mcp_server/server.py
```

It runs over stdio. You don't need to keep it open for the app: the backend starts its own copy of `mcp_server/server.py` for every run. Run it by hand only to check it starts. To use the tools from Claude Code, open the project folder (with the venv active) and `.mcp.json` connects `campus-customs`.

## 4. Start the FastAPI backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The API is at http://localhost:8000 (interactive docs at `/docs`). It allows the dashboard origin `http://localhost:5173`. The routes are listed in `output/harness.md` §7.

## 5. Start the React board

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The board calls `http://localhost:8000` (override with `VITE_API_URL`).

## 6. Before a full three-ticket run: reset the database

1. Reset first: click **Reset shop** on the board, or `POST http://localhost:8000/api/reset`, or `python -m backend.reset_db` (step 2). The original database is only read, and the audit trail is kept.
2. Pick ticket **101**, click **Start the agent team**, and watch the agents live until the red seal shows it resolved. Then do **102**, then **103**.
3. Payments the agents file appear under **Awaiting your seal**. Type your name under "Approving as" and click **Approve & pay**; checking drops on screen. Agents can only *request* money; nothing moves without a person.

Expected result of a full run: 101 files invoice 501 ($840), 102 files rent ($2,400), and 103 is escalated (the vendor is on hold and cash is short). Approving both takes checking from $3,400 to $160.

Tip: if the project is in OneDrive or Dropbox, pause syncing during a run. The sync can trigger `--reload` and restart the server mid-run.

## Safety in one paragraph

Payments need a named human, enforced in code: the approve tools are never given to an agent. Cash can never go negative, and amounts are always computed from the database. Each agent sees only the tools its job needs, and read tools open the database read-only. Customer messages stay on the board as drafts. Every agent step, hand-off and human decision is appended to `output/audit_trail.json`. Full details are in `output/harness.md` §6.

# The Lethe Desk: dashboard design

`frontend/`: React + Vite + TypeScript. Start it with `npm run dev` (port 5173). It calls the FastAPI backend at `http://localhost:8000` (the default in `src/api.ts`; set `VITE_API_URL` to point it somewhere else), and the backend's CORS setting allows `http://localhost:5173`.

## The idea: a Ninth House desk

Campus Customs is a Yale shop, so the desk borrows the dark-academia mood of Leigh Bardugo's *Ninth House*. In the novel, Lethe, the ninth house, exists to keep watch over what the other secret societies do. That is the human's job in this system: five agents do the work, and a person oversees them and holds the only power to move money. The theme isn't decoration on top of the app; it explains the app's rules. The name, **The Lethe Desk**, and the line under it, *"Five houses do the work. The ninth keeps watch, and you hold the seal,"* tell a new user the trust model before they click anything.

The theme stays a light skin. **Every label that matters is plain business English first** ("Start the agent team", "Approve & pay", "Checking"), and the flavor sits beside it in smaller italic serif. Someone who has never read the book can run the desk without guessing. No text from the novel is used, and the house assignments are playful nods, not claims about the book's lore.

## Layout: three columns, one job each

| Left: **The Board** | Center: **The session** | Right: **The Vault** |
|---|---|---|
| The 3 tickets as cards (number, subject, requester, type, SKU/lease/invoice), then **The Houses**: the 5 agents with a live status line each | The selected ticket and its **Start the agent team** button, the end-of-run **summary**, and the **live agent activity** feed | The **checking balance**, payments **awaiting your seal** with Approve / Reject, and the ledger of sealed payments |

The eye moves left to right in the order you work: pick the work, watch it happen, sign off on the money. Each column answers one question: what's on the board, what's happening now, and what it costs. Under 1,180 px the Vault drops below the other two columns, and on a phone everything stacks.

## Telling the agents apart

Each agent is one of the Yale houses, with its own **color**, **engraved sigil** and **one-line description**. Color carries through everywhere the agent appears: its roster card, its feed lines, its summary card and its hand-off arrows. You can follow one agent down a long feed by color alone.

| Agent | House | Sigil | Color | Why it fits |
|---|---|---|---|---|
| Boss | **Lethe House** | an open eye | candle gold | the watcher that reads every ticket and sends the work out |
| Inventory | **Scroll and Key** | a key | teal | unlocks the stockroom: what's on hand, what's short, who can restock |
| Accounting | **Skull and Bones** | crossed bones under a coin | blood red | reads the ledger's future: cash, invoices, margins |
| Facilities | **Book and Snake** | a book with a curling line | moss green | keeps the walls standing: the lease and the rent |
| Customer Service | **Aurelian** | a quill | violet | keeps the shop's word: drafts every message, sends none |

In **The Houses** roster, each agent has a small **lamp**. It's dark when idle, flickers in the house color while the agent works, and glows steadily once it has reported back. The status line says what it is doing right now, for example "Calling check_stock", "Handing off to Accounting", "Waiting on Inventory" or "Reported back". Agents the Boss never called say so ("Not called on this ticket"), which makes a lean plan visible.

## Watching the agents live

The center feed polls `/api/events` every second while a run is going, so steps appear **as they happen, not at the end**. Each line has the agent's sigil, its name in house color, a verb and a timestamp:

- **calls** `tool_name` with the arguments, in mono type, so you can see exactly what it asked the MCP server
- **← tool answered** with the useful fields pulled out (`on_hand: 8 · shortfall: 12 · can_fill: false`) instead of raw JSON
- ***hands off to Accounting***, in italic serif, with the exact task it passed on
- **reports back** with the agent's one-line conclusion

Three pulsing dots show the team is still thinking. A meter keeps a running count of model calls, tokens and estimated cost at gpt-6-luna prices. While a ticket runs, its card says **In session** and breathes with a soft gold glow, the button shows a lit candle with "The team is working…", and the other Start buttons lock, because only one run happens at a time.

## Resolved tickets

When a run ends, the backend marks the ticket **resolved**, and the desk shows it two ways:

- On the board, the ticket gets a small **red wax seal** marked "R" in place of its "Open" tag.
- In the center, a **summary card** stamps down above the feed with a larger wax seal. It shows the Boss's decision in words ("Wait for restock", "Pay, pending your approval"), what the ticket asked, then **one card per agent that worked**: what it concluded, the MCP tools it used, and who it handed off to. Any customer message is folded underneath as a parchment-style **draft marked "not sent"**, so it's clear nothing left the shop.

## Cash and approvals

**The Vault** shows the checking balance as the largest number on the screen, because money is the one thing a human must watch. Under it:

- a gold bar for how much of the opening $3,400 is left, with the part already promised to pending requests hatched in red
- the balance you'd have if everything pending were approved

**Awaiting your seal** lists every payment or purchase the agents filed: the type, the amount, the payee, the agent's reason, and **what checking would be after you pay it**. That number turns red, with a warning, if paying would push cash below zero; the backend would refuse it anyway. To approve, you type your name once under **Approving as** (it's saved). An agent's name is rejected, so a person is always on record. Then you click the red wax **Approve & pay** button.

When you approve, the balance updates and a red **−$2,400.00** drops off the number, so you *see* the cash go down. The bar shrinks and the payment moves to **Sealed payments** with your name on it. **Reset shop** in the header restores the original database for a fresh run; it asks for confirmation, keeps the audit trail, and is disabled during a run.

## What makes it feel special

- **The Grays.** Faint, blurred, ghost-like shapes drift behind everything (in the book, Grays are ghosts). They're barely there when the desk is idle and gather when the agents start working, so the room itself tells you the house is busy.
- **Candlelight, not dashboard blue.** Near-black ink with a warm parchment white for text and gold for anything that needs you. A few glowing details (lamps, the candle, the gold Start button) guide the eye without clutter.
- **Typography that feels like Yale.** Cormorant Garamond, an old-style serif, for headings, house names and the hand-off lines. Inter for anything you need to read quickly, and JetBrains Mono for tool calls and money, so data never looks like decoration.
- **Ritual moments for real decisions.** The wax seal stamps down when a ticket resolves, and approving is literally "putting your seal on it". The two moments that matter most, a finished ticket and money leaving the shop, get the most ceremony.
- **Honest by design.** The feed shows the actual tool calls and answers, so you can check the agents rather than trust them. Unfinished runs are labelled "interrupted" instead of looking stuck.
- **Calm by default.** Motion is slow and quiet, and the whole desk respects the system "reduce motion" setting.

## Files

`src/App.tsx` (layout and polling), `src/derive.ts` (turns audit events into agent states, feed lines and the summary), `src/houses.tsx` (house colors, sigils and copy), `src/api.ts` (typed calls to the Problem 7 routes), `src/index.css` (the look).

# AI_prompts.md

Log of what I typed to my vibe coder for Homework 5 (Campus Customs Multi-Agent Operations). One section per problem: the problem number and title, at least one prompt in my own words, and a follow-up prompt if I needed one, with one sentence on what was lacking after the first.

---

## Problem 1: Vibe coder prompts

**Prompt:**

> pls create AI_prompts.md and keep it updated as we work, this file is meant to be the graded log of what I type into you
>
> for reference we'll work section by section for each problem and each section has to contain the following: the problem number & title, at least one prompt you used in my own words and one follow-up prompt if we needed it and one sentence on what was lacking after the first - got it my lil vibe coder?

**Follow-up:** None needed.

---

## Problem 2: Study the Campus Customs database

**Prompt:**

> alright lets open data/campus_customs.db and review the data holistically, meaning every table, every field
>
> i need you to copy the original file to data/campus_customs_new.db pls note that later problems update the working copy -- show me the 3 open ticket so we can see how they link to toher tables, also understand this yourself
>
> we're going to need to start output/harness.md and for each table i need you to list the fields and one short line on why that table matters for the agents - let me know if you need additional input and pls note that we willl grow this harness file in later problems

**Follow-up:** None needed.

---

## Problem 3: Build the MCP server

**Prompt:**

> we're gonna get flirty - lets write an mcp server in mcp_server/ using FastMCP (can you explain to me what FastMCP is?) it should talk to data/campus_customs_new.db -- at this time don't connect or run it in this problem
>
> write three tools that we'll need for the tickets in the database and keep the names clear - don't invent any data, only use info in the database....understood?
>
> you want to give me a list of tools that may be helpful and recommend 3 and i'll do the final call?

**Follow-up:**

> oh good call ty -- for problem 3 panel b:
> in the output/harness.md I'd like you to list each of the three mcp tools and for each tool pls include which table it reads, what ticket it helps to unlock (this should be 101, 102, or 103) and also a single sentene on why that tool is the right one for that ticket... we need to tie the tool to the ticket, be as specific as possible, vaue lines score v low and remember we're optimizing our grade babbbby
>
> also add a short mcp_server/README.md file - this  needs to explain what the mcp server is for, what database file it uses and what three tools it has.... let me know if you feel additional info would be helpful - I'd like to go with your recommendations

**What was lacking after the first:** My first prompt only covered building the server and picking tools, so it didn't ask for the harness entries tying each tool to a ticket or for `mcp_server/README.md`.

---

## Problem 4: Add the MCP server to vibe coder and test each tool

**Prompt (connect):**

> lets add the mcp server to this project so that it/you can call the tools - we need to save the connection json text in .mcp/json at the project root if thats how you saved local mcp server lists, if not then however you do
>
> with you now connected, i need you test the three mcp tools we used and the evidence has to be saved in output/mcp_smoke.json
>
> for each tool, you need to include the prompt i asked the vibe coder, the tool name, and the tool output - which has to match values in data/campus_customs_new.db

**Prompts (one per tool test):**

> ok only use the check stock tool from my campus custums mcp server for this, dont go search the databse yourself. check CC-HOOD-NAVY size M qty_needed 20 then run it agian for CC-TEE-WHITE size S qty_needed 1 -- show me exactly what the tool gives back both times. after that search the invetory table in data/campus_customs_new.db yourself and go thru it one by one, hoodie should be 8 on hand and 12 short and tee should be 0 on hand and 1 short -- just tell me straight up if each one matchs or not

> run check vendor hold from my campus custums mcp server for vendor 1 and show me exactly what it gives back -- then go check it yourself in the db. todays date from the desk table, lead days from vendors, and any open invoices for vendor 1 in invoces. what im expecting is Bulldog Print Co, 5 day lead time, invoice 501 for $840 still open due 2026-08-28 so its 3 days late as of 2026-08-31, which means they cant ship. does the tool agree on everything? if not tell me where its getting it wrong

> run get rent due from my campus custums mcp server for lease 1 and show me exactly what it gives back. check it agianst the leses, desk and cash acounts tables -- rent should be $2,400 due 2026-09-02 which is 2 days out from 2026-08-31, and checking is at $3,400 so it covers it with $1,000 left over. make sure every number lines up and that the tool didnt change anything in the tables, it should only be looking not editing

**Follow-up:** None needed.

---

## Problem 5: Build the agent team and grow the MCP tools

**Prompt (Panel A):**

> freaking sweet! yes i am ok now build the agent team for campus customs using pydanticai, boss, inventory, accounting, cacilities and customer service
>
> each one needs its own prompt, its data types and its agent loop, and they all need to be able to hand work off to each other, any agent to any other agent... put the prompts in backend/prompts/ with one file per agent and data types go in backend/models.py and the agent files go under backend/ - i dont care how its laid out as long as its clear which file is which role -- remember use my portkey api and ONLY gpt-6-luna for every single agent, no other model
>
> for the prompts make them detailed.. i dont want short generic ones each agent should know its job, what its allowed to do and not do, and the shop rules that matter for it. like accounting cant pay anything without me approving it and cash can never go negative, inventory has to check whats actually in stock, that kind of stuff -- cover everything that agent would run into

**Prompt (Panel B):**

> add whatever tools the agents need to my campus custums mcp server so they can actualy work the open tickets. all the shop info has to come from the mcp server off data/campus_customs_new.db, DO NOT make some second set of shop tools on the side that skips the mcp - if you think you need to or something tell me and we can work it out
>
> hook the agents together so they add to output/audit_trail.json as they run. every step of every agent loop should save enough that i could go back later and see what happend and why, it needs to add on to the file each time, dont wipe it out when it runs again
>
> then in output/harness.md list every agent and every mcp tool, including the new ones from this step, and which table each tool uses. add a short safety section too, what guardrails a real buisness would want when agents are dealing with real customers and real money, plus limits that keep token use under control
>
> update mcp_server/README.md so the tool list matches what we have now
>
> pls tell me if you need anything more from me for pane b

**Follow-up:** None needed.

---

## Problem 6: Plan the three tickets

**Prompt (Panel A):**

> before we hookup the backend i want to write down what i think the team will do on each open ticket... make output/desk_tickets.html, it should just open when i double click it, not require a server
>
> one tab per ticket so 101, 102 and 103, plus an empty cash tab and an empty reflection tab for later, those can be blank or just say coming later for right now. On each ticket tab, only fill in an expected section, leave a spot for an actual section but keep it empty, ill fill that in after we run the agents, make sense?

**Prompt (Panel B):**

> heres what i expect for each ticket, put it in the expected section on each tab - dont change my plan, but feel free clean up the wording a little:
>
> 101 -- boss calls Inventory first since the customer wants a white tee in S and we need to know if we even have it
> inventory finds 0 on hand so it hands off to accounting to see if we can reorder from vendor 1 -- accounting finds the correct invoice for amount and if we owe money then the vendor is on hold and cant ship, if that happens accounting suggests paying it but i have to approve it first and cash cant go negative - then customer service writes the customer back with whats going on and a realistic timeline (god help us all) tools are check_stock, check_vendor_hold - no facilities
>
> 102 -- boss calls cacilities first because its a rent question and facilities is in charge of the lease
>
>  facilities finds the amount and due date then hands off to Accounting to make sure checking can cover it and set up the payment for my approval. no inventory or customer service since there's no customer or product. tools would be get_rent_due, plus whatever reads cash_accounts
>
> 103 -- boss calls Inventory first because its a big hoodie order and we need to know how many we actually have, inventory hands off to Accounting to work out the discount and check if the vendor can ship whatever we're short... then Customer Service sends the customer the quote and timeline. Facilities isnt needed and tools are estimated to be check_stock, check_vendor_hold

**Follow-up:**

> ok does this addres....
>
> 101 -- boss starts with get_ticket, then calls Inventory first because the customer wants a white t and we need to know if its in stock. if its not, inventory hands off to Accounting to find the vendor and see if we can reorder. accounting will probably find we owe them an overdue invoice so theyre on hold, so it files that payment for my approval, nothing gets paid till i ok it. Customer Service drafts a reply to the customer, no emailing, it just stays on the board - we cant promise a date until the invoice is paid so the reply should say theres no confirmed date yet. Facilities isnt needed. boss closes it out with update_ticket_status. tools: get_ticket, check_stock, list_vendors, check_vendor_hold, request_payment, post_draft, update_ticket_status
>
> 102 -- boss starts with get_ticket, then calls Facilities first because its a rent question and facilities owns the lease. facilities pulls the rent due, which already shows the balance, and hands off to Accounting to double check the cash and file the payment for my approval. no Inventory or Customer Service since there's no customer or product - boss closes it out with update_ticket_status. tools: get_ticket, get_rent_due, get_cash_position, request_payment, update_ticket_status
>
> 103 -- boss starts with get_ticket, then calls Inventory first because its a big hoodie order and we need to know how many we actually have... inventory hands off to Accounting to work out the bulk discount and see if we can restock what were short. this probably gets stuck on the same thing as 101, the hoodies come from the same vendor thats on hold. and even if i approve that invoice and the rent there might not be enough cash left to pay for the restock, so i expect the order to get refused. Customer Service drafts the quote for the customer on the board, no emailing, and says the rest is on hold. Facilities isnt needed. boss closes it out with update_ticket_status. tools: get_ticket, check_stock, check_discount, check_vendor_hold, post_draft, update_ticket_status

> ca you fix these things/ *(after the vibe coder noted: tickets with a pending payment end "awaiting approval" rather than closed, 103 also needs request_payment since that's the tool that refuses the restock, and in 101 Inventory, not Accounting, looks up the vendor)*

**What was lacking after the first:** My first plan listed only `check_stock` and `check_vendor_hold` (missing `get_ticket`, `request_payment`, `post_draft`, `update_ticket_status` and `check_discount`), had Customer Service "send" the quote instead of drafting it, and didn't predict that ticket 103 would be blocked by the same vendor hold and tight cash.

---

## Problem 7: Backend routes

**Prompt (Panel A):**

> next i need a backend the react dashboard can talk to (thats the next problem) - in backend/main.py use fastapi and add routes that give back the 3 tickets and if each one is open or resolved, take a ticket id and run the agent team on just that ticket, give back the recent agent events, what each agent said and whih tools were used - so the board can refresh - approve a payment or purchase once i click approve. the agents only set the payment up, this route is the only thing that actually changes cash and it cant let cash go negative - give back the current checking balance from cash_accounts, reset the database back to the original values so i can do a fresh run
>
> copy it from data/campus_customs.db, dont ever change that original file, and dont wipe the audit trail when it resets -- also make sure the react app will be able to call it from the browser without getting blocked

**Prompt (Panel B):**

> start the server from the backend/ folder with uvicorn main:app --reload --port 8000 and make sure it comes up on http://localhost:8000 then hit each route once to show it works. after that add the routes to output/harness.md, one line each with the url and what it does
>
> did you get everything you need?

**Follow-up:** None needed.

---

## Problem 8: Agent dashboard

**Prompt (Panel A):**

> ok now build the dashbaord in frontend/ with React + Vite + TypeScript and have it call the routes we made in prob 7... did we do everything right in prob 7 to make this possible?
>
> at minimum it needs to list all 3 tickets and let me pick one and start the agent team on it -- while its running i want to see each agent and what its saying and doing, live not just at the end
>
> when the run finishes mark the ticket resolved and show a short summery of what each agent did on it. if theres a payment or purchase that needs approving, it should ask me and let me click approve, and show the checking balence somewhere so i can watch it go down after i aprove something. and make it look good, be creative with it -- this is supposed to be a real desk people would want to sit at, not a boring admin page - right now i'm reading ninth house, what if we made it ninth house themed? or would that be weird - we've got some spooky yale vibes in the book we could utilize i feel

**Prompt (Panel B):**

> point the frontend at the backend on http://localhost:8000 and make sure the backend allows http://localhost:5173 so the browser doesnt block it - start it with npm run dev and open it up so i can pick a ticket and watch the agents go. then write output/design.md about how the dashbaord looks and why -- the layout and how you can tell the agents apart and how resolved tickets and cash show up and the creative stuff that makes it feel special and like something people would actualy enjoy using

**Follow-up:** None needed.

---

## Problem 9: Resolve the tickets

**Prompt (Panel A):**

> before the full run reset data/campus_customs_new.db again so we start clean and tell me what checking is at right after the reset. ill run all three tickets on the board 101 102 103 til each one is resolved
>
> after that open output/desk_tickets.html from problem 6 and fill in the actual section on each ticket tab from this run -- which agents worked what they handed off to who and which tools they used, dont touch my eexpected sections, i want to be able to compare them side by side

**Prompt (Panel B):**

> for 9b, fill in the cash tab in output/desk_tickets.html -- checking after the reset, how each ticket changed cash and why, then the ending balence. search cash_accounts to make sure the ending number matches and tell me if it doesnt. save output/resolved_tickets.json with each tickets id, status, outcome, what each agent did and any approvals i gave
>
> make output/resolved_board.html with a screenshot of the board for 101 102 103, it has to open on double click. check the runs got added to output/audit_trail.json without wiping it, then finish output/harness.md -- tables, mcp tools, the five agents, api routes, dashbaord and safety rules

**Follow-up:** None needed.

---

## Problem 10: Reflection

**Prompt (Panels A and B), part 1: ticket 101:**

> ok open and fill in the reflections tab, we'll need to be detailed and thorough and I think this has to come from me - for 101 first panel a (am i right for the last two bulletpoints i can answer when i'm done with the ticket specific analysis?)
>
> for 101 --
>
> The run pretty closely matched the plan - inventory went first, cacilities stayed out, the invoiced amt waited for approval, and the draft did't promise a date
>
> some differences though were that the Boss sent all the tasks out at once instead of the inventory to accounting chain, customer service asked Inventory to re-check, and the desk marked the ticket "resolved" while the payment was still waiting for me to resolve it
>
> One agent instead would have likely resulted in a running the steps in one straight line in less model calls because each step depends on the one before it and every tool should be a quick lookup so splitting the work across agents added repeated calls (looks like the ticket for ex was read 5 times) and context maybe lost between hand-offs

**Follow-up:**

> good call out - for 101 it performed well - the outcome was correct and safe, meaning it didn't make a payment without your approval or promise a date and nothing was sent to the customer - the main drawback was it was less efficient than it needed to be because a straight forward step by step ticket was split across four agents, which led to more model calls and repeated the same lookups

**What was lacking after the first:** My first 101 answer compared the run to my plan and to a single agent, but it never gave my actual verdict on how well the agents performed and why.

**Prompt, part 2: ticket 102:**

> ok 102 - It closely matched the expected plan in that facilities went first, only facilities and accounting were involved, and the rent was filed for approval - it differed in that the boss called accounting directly instead of facilities handing off to it and accounting also checked invoice 501 so it could rank both bills, and the desk again marked the ticket "resolved" while the payment was still pending...so I mean it wasn't really resolved
>
> on one agent, this one was probably even more a one-agent job than 101 - in the log, it looks like accounting re-ran facilities' get_rent_due lookup itself, so facilities added like nothing it needed, and a single agent could have finished in less calls by the looks of it (can I put numbers to this?)
>
> It did perform well though in that the rent was filed but not paid, cash never went negative, and Accounting usefully advised paying the overdue invoice first, which left $160 once both are paid - so it was successful in the core functionality. on the downside, it was a bit wasteful because a lookup-and-file ticket was split across two specialists who repeated each others work

> can you also add the numbers in for 101?

**Prompt, part 3: ticket 103:**

> before i write up 103, can you give me number of calls and tokens used so i can compare?

> ok 103 -
>
> the run matched expectations pretty closely again - inventory went first, facilities wasn't called, the vendor hold blocked the restock (sad), customer service drafted without sending, and the ticket was escalated which i thought it might be. but there were differenes - accounting never tried a restock order, so request_payment was never called and the Boss also got the cash wrong: it said the $160 left wasn't enough to cover invoice 501, but that $840 invoice was already counted as request #1 from ticket 101....sooo I mean it wasn't accounting for things quite correctly
>
> this one was probably the worst case for splitting the work, it had 26 calls...Inventory and Accounting each did their checks 2x because Customer Service sent them the same questions the Boss had, and one hand-off loop had to be blocked... a single agent holding all the facts in one context would not have had to re-ask anything and it would likely have caught that the invoice was already pending (just a guess)
>
> this one was the worst out of the three imo although the run did stay safe, it just reasoned pretty poorly. While nothing was promised, approved/paid, the escalation was becaseu the invoice was counted 2x. Accounting also seemed to answer the greatest possible discount which no one asked for.... more agents means more hand-offs (makes sense) and each hand-off lost context and repeated work.... does this always happen with agents? just lookiing for an answer

**Prompt, part 4: three new problems the team could solve:**

> three that we could solve with the current tools - 1.) we could do a morning status report for every open ticket and report back whats blocked - this would require the boss to work and then whichever specailists each ticket needs, itd use the tools already built, most likely list_open_tickets, get_ticket, update_ticket_status ; 2.) we could do a weekly bill check that tells us what we owe, whats pending, and answer if we can cover it all, this would call the boss agent who would call accounting and facilities, and tools list_payment_requests, get_cash_position, get_invoice, get_rent_due ; 3.) once invoice 501 is paid (i paid it right? ) then we can reorder the hoodies we're short so inventory could talk to accounting - tools: check_vendor_hold, list_vendors, request_payment(kind="purchase_order") and then it should wait for human approval

**Prompt, part 5: three new problems the team couldn't solve:**

> three that it couldn't  solve with the current tools - 1.) right now it can't find a baackup vendor so like when we can't get an item in it can't procure from a new source, it'd need tools to search the web, get quotes and then add a vendor... so we'd need a new agent within this architecture, maybe a procurement agent; 2.) sent repair requests to landlord when something is broken at the shop or needs maintenance, we'd need to add tools to create maintenance requests then work with the contractor to schedule service - so schedule service tool as well, assuming the land lord had to find the contractor, if we also have to find the contractor then take it out of rent or something we'd need a find contrator tool as well - this could fit within the facilities agent but with more tools added in; 3.) take payment or issue a refund for an order - this could really automate things, we'd need tools to create the order, charge the customer, and issue the refund - this would probably need to be a new agent, like a Sales agent and refunds with need human approval
>
> then let me re-do 3, thanks for calling it out

**Follow-up (redo of "could solve" #3):**

> for 3 - we can't restock though? i get what you're saying about current workflow but like my point was more if restock was allowed because we have say more than 160 in the account, we couldn't do it - dos that not hold up

> ok nice - restock the items at zero that I flag (like the size small t-shirt and the crest mug)- given we have enough cash (cash can't go negative) we could restock with tools we already built - agent called would be inventory confirms items at zero with check_stock and finds the vendors with list_vendors and check_vendor_hold (Bulldog Print Co is no longer on hold now that invoice 501 is paid), and Accounting files two orders with request_payment and wait for my approval

**What was lacking after the first:** My first #3 (reorder ticket 103's hoodies) wasn't a new problem and would have been refused at $160 checking, and my next version assumed the team could find zero-stock items on its own, when `check_stock` only checks items I name.


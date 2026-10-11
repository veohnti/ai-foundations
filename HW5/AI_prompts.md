# Problem 1: Vibe Coder Prompts

## Initial prompt (verbatim)

Problem 1: Vibe Coder Prompts

/folder-workspace in HW5 and /ai-prompt-tracker

## Summarized follow-up prompts

_No follow-up prompts yet._

_What was missing in the original prompt: Nothing identified yet; follow-up prompts have not been provided._

# Problem 2: Study the Campus Customs Database

## Initial prompt (verbatim)

Problem 2: Study the Campus Customs Database

Step 1) unzip data.zip
Step 2) open data/campus_customs.db and copy that original file as data/campus_customs_new.db. Later problems will update that COPY
Step 3) read through campus_customs.db to understand the file (look through every table & field
Step 4) Analyze the three open tickets so we understand how they link to other tables (and let me know in the chat)
Step 5) start output/harness.md list the fields for each table and describe, in one sentence, why that table matters for the agents
Step 6) Just some notes: we will keep growing the harness file over time. Additionally, in this HW assignment, we will use my PORTKEY_API_KEY. And, once the time comes, we will ONLY USE GPT LUNA for every agent. Keep that in mind.
Step 7) another piece of context: we will never actually email or call real customers, everything (drafts) will stay on the board

## Summarized follow-up prompts

_No follow-up prompts yet._

_What was missing in the original prompt: Nothing identified yet; follow-up prompts have not been provided._

# Problem 3: Build the MCP Server

## Initial prompt (verbatim)

Problem 3: Build the MCP Server

Step 1) Write an MCP Server in mcp_server/ by using FastMCP. It will communicate with data/campus_customs_new.db 
Step 2) in this problem, we do not need to connect it or run it!
Step 3) Every agent in this HW assignment will use the tools that are in this MCP server
Step 4) We will add more tools to it later, but for now, please add the following three tools we will need for the tickets in the database. Based on the open tickets, I think those three tools are: read a ticket, check stock, watches cash and invoices. I'm not sure if those are the three tools however, so please check to see if you agree and feel free to build 3 different tools you think are more pertinent based on the data you have and that I might have missed
Step 5) Keep the names of these tools very clear and NEVER INVENT ANY DATA. Only use the information that is in the database
Step 6) Update output/harness.md to list the three MCP tools. For each tool, please explain which table it reads from, which ticket it helps unlock/solve (101, 102, or 103) and a brief statement (one sentence) on why that is the correct tool for that scenario. Tie the tool to the ticket and avoid vague statements to describe the tool
Step 7) create a short mcp_server/README.md that describes what the MCP server is for, which db fil it uses, and the 3 tools it has so far.

## Summarized follow-up prompts

_No follow-up prompts yet._

_What was missing in the original prompt: Nothing identified yet; follow-up prompts have not been provided._

# Problem 4: Add the MCP Server to vibe coder  and test each tool

## Initial prompt (verbatim)

Problem 4: Add the MCP Server to vibe coder  and test each tool

Step 1) Add the MCP Server to this project so you (Claude Code) can call the tools. 
Step 2) Save the connection JSON text in .mcp.json at the project root. 
Step 3) connect to the MCP and test the 3 tools!
Step 4) I want to be able to check your work so please save the evidence in a new file: output/mcp_smoke.json
Step 5) For every tool, please provide 1) the prompt to test it (below) , 2) the tool name, and 3) the tool output (which must match values in data/campus_customers_new.db ) 
Step 6) Prompt for tool 1:  get_ticket_with_links(ticket_id): Test tickets 101, 102, and 103 to verify that each ticket and its linked lease, invoice, and vendor records are retrieved accurately, especially ticket 101’s linked $840 invoice that is three days overdue.
prompt for tool 2: check_stock_and_price(sku, size, qty_requested): Test the SKUs and quantities associated with tickets 101 and 103 to verify stock availability across sizes, quantity shortages, unit cost, and list price, specifically confirming the $22 cost and $58 list price relevant to ticket 103’s discount decision.
Prompt for tool 3: get_cash_and_obligations(): Verify that the tool accurately returns the checking balance, outstanding invoices and overdue days, rent due, and recorded payments, then independently calculate whether paying all outstanding obligations correctly leaves $160 in cash.

## Summarized follow-up prompts

_No follow-up prompts yet._

_What was missing in the original prompt: Nothing identified yet; follow-up prompts have not been provided._

# Problem 5: Build the Agent Team and grow the MCP tools

## Initial prompt (verbatim)

Problem 5: Build the Agent Team and grow the MCP tools

Step 1) Now we are going to create the agentic team for Campus Customs. I want to build the following agent team using PydanticAI: boss, inventory, accounting, facilities, and customer service. 
Step 2) These 5 agents will need prompts, models, and agent loops so they can work together, delegate tasks, and be fully connected
Step 3) Create and put the agent prompts in: backend/prompts/ where there is one file for each agent
Step 4) place the data types in backend/models.py and place the agents in backend/ . The layout doesn't matter as much for the 5 agents as long as their names are very clear! 
Step 5) As I mentioned in a previous prompt, please use the PORTKEY_API_KEY and ONLY USE got-6-luna for each agent (otherwise it will cost me too much!)
Step 6) I will need you to flesh out the details for the prompts for each model but I want to give you some direction as well. For each prompt, make sure it is not just a short prompt, but rather, detailed and covering all of the scope that this agent might have. So initial prompt that you can build off of: for the boss: it reads the ticket, knows who to delegate to (which agent), and makes final calls. For the inventory agent: checks stock sku and sizes, determines and find shortfalls, and can figure out which vendor to use to restock. for the accounting agent: keeps an eye on cash and  invoices. can check margins, and prepares payments or purchase orders for human approval (I am the human approvale). Facilities agent: is in charge of taking care of the shop's space side of things (such as leases and rent). customer service agent: drafts messages for customers (but never send them!!!).
Step 7) Some rules for the shop: desk.date_today means today for the shop. You can use that to determines what is overdue. vendor lead times come from the vendor table (useful for inventory agent). If a vendor has an open invoice, it will not ship new products. human approval is necessary for every payment. if a payment is made, the appropriate table needs to be updated. If we do not have enough cash, the pay tool used by the agent involved in this must refuse (i.e., no negative balances). cash will only go out in this assignment - for this assignment, no monies come in. before a full run to resolve tickets , the database must be reset to original values. As i mentioned above, DPO NOT EMIAL customers or real vendors. All drafts must stay on the board.
Step 8) make sure to match some of the rules I mentioned above in step 7 to step 6 for the appropriate agents. 
Step 9) Add any other tools (to the MCP server) these agents might need to resolve open tickets. Facts about the shop comes from the MCP server over data/campus_customs_new.db
Step 10) do not invent a second shop tools layer  that bypasses the MCP
Step 11) create the agents so that every run is logged to output/audit_trail.json. This must be an append and you must not wipe the file with each run (it should only grow through append so no erasing)
Step 12) Update output/harness.md by listing each agent and each tool they have access to (from MCP), including the ones we are adding in this problem. Also include which tables the tools use.
Step 13) in the harness.md file, also add a short safety section which include the guardrails we would want for these agents, especially since they are touching/interacting with money and customers. Ensure the safety rules are tailored to the context in which we are creating them. Also inlcude limits that keep token use in check so we don't burn through money.
Step 14) update mcp_server/README.md so the tool list matches what we now have

## Summarized follow-up prompts

### Follow-up 1

(Raised while reviewing the dashboard, with a screenshot of a customer draft.) Workers must be able to talk to each other directly, not only boss → worker; the full connectivity asked for earlier should actually be used and visible. Customer drafts also reveal too much: customers should not be told that the shop paid for a restock or who its vendors are.

**What was missing in the original prompt:** "Fully connected" didn't say that specialists should actively consult each other in practice. The rule "drafts for customers" didn't define what information is internal-only (vendor names, payments, invoices, approvals) and must stay out of customer messages.

# Problem 6: Plan the 3 tickets

## Initial prompt (verbatim)

Problem 6: Plan the 3 tickets

Step 1) Before we wire the backend, we should plan what to do with each ticket.
Step 2) To do so, I would like you to build an html output/desk_tickets.html. this page will allow us to double click on the html so it opens a page where we can see tickets 101, 102, and 103 (each on a separate tab) 
Step 3) Add empty tabs for "Cash" and "reflections" that we will add data to in later problems (they should be empty for now)
Step 4) for each ticket tab, I want an "actual" and a "expected" section. In this problem (problem 6) we will only fill the expected section. 
Step 5) Expected section: these sections will have 3 types of entries: (1) who the boss should call first, and why, (2) all the delegations that happen, and (3) which MCP tools I expect that run to see.
Step 6) Filling the expected section: (101) The boss should call the inventory agent first because the order involves a tee that we know is not in stock and we may need to find a vendor to re-supply. A delegation that might happen is to delegate to the accounting agent to figure out if we have money to restock and another delegation could be to customer service to let them know of the outcome. it could use the tools "get_ticket_with links", "get_vendor_restock_options". (102) the boss should probably call the facilities agent first since they are in charge of all space related questions. A delegation that might happen would be to talk to the accounting agent since it involves rent that is due. Tools it might call are: "get_cash_and_obligations", and "list_approval_requests". (103) boss will likely call on the inventory agent since it involves a bulk order for which we may not have full stock. a delegation that may happen is accounting to check for margins, and will need human approval as well i think. finally, tools that might be called are: "request_payment_approval" and "check_margin"

## Summarized follow-up prompts

### Follow-up 1

Asked for a direct link to `output/desk_tickets.html` that can be clicked and opened in a browser.

**What was missing in the original prompt:** The prompt asked for a page that opens on double-click but didn't ask for the file's browser URL (`file://` path) to be provided along with it.

# Problem 7: Backend Routes

## Initial prompt (verbatim)

Problem 7: Backend Routes

Step 1) In backend/main.py use FastAPI and add routes that do the following: (a) return the 3 tickets and whether each is open and resolved; (b) take a ticket id and run the team of agents on that ticket; (c) return agent events (which is what each agent said, and which tools they used) so that the board can refresh; (d) after a human approves by clicking "approve", approve the payment or purchase (the agent only prepares the pay; this route is what actually changes the cash); (e) return the current checking balance from cash_accounts; (f) reset the database to the original values if i want to try a fresh run
Step 2) from the backend folder, (backend/) start the server with uvicorn main:app --reload --port 8000
Step 3) in harness.md (in output folder) have each route listed in one line each (what it does, and what url)

## Summarized follow-up prompts

_No follow-up prompts yet._

_What was missing in the original prompt: Nothing identified yet; follow-up prompts have not been provided._

# Problem 8: Agent Dashboard

## Initial prompt (verbatim)

[Two images attached: a table-setting photo with a color palette strip (royal blue, coral, peach, silver) and a "PERFECT THOUGHTS" typewriter-font sample.]

Problem 8: Agent Dashboard

Step 1) now we are building the front end with React + TypeScript + Vite. The page should call the routes we built in the last problem (a through f)
Step 2) the board should have the following: list all three tickets, allows the user to pick one ticket which starts the agent team workflow on that ticket, show each of the agent (what they are thinking, saying, and doing, WHILE the ticket is running), mark a ticket as complete once it is resolved when the run is complete, show a summary of what each agent did for that ticket (the summary can be short), let a human approve a pay or purchase when asked, show the checking balance (it should go down after an approved pay) 
Step 3) I would like the dashboard to look good! I want to see the layout first before suggesting edits to it but please look at the font (type writer style) and color palette I attach for inspiration (i like the background to be white but allow for the pops of color I included in the pallete
Step 4) the front end must communicate with the back end at http://localhost:8000
Step 5) on the beckend, allow Vite page origin (usually localhost:5173)  so the browser is allowed to call those routes
Step 6) Start the board with npm run dev
Step 7) write output/design.md with what i choose for the dashboard look (like color palette in rgb, typewriter font, and I'll give additional design suggestions later after I see the first draft) and include a why (no need to include a placeholder serction here for my later instructions, just keep it updated with the current design choices).

## Summarized follow-up prompts

### Follow-up 1

After seeing the first draft: make the boxes more pronounced, since they fade into the white background. Add much more color pop to match the vibrant inspiration photo instead of a mostly white, plain look. Make delegation between the boss and agents clearly visible, for example as a web of lines connecting all agents that lights up in the bright colors and shows the direction of each hand-off. Keep it intuitive and easy to work with.

**What was missing in the original prompt:** The original asked for the palette only as "pops of color" on a white background and gave no direction on box contrast. It also asked to show what each agent is doing, but not to visualize the delegation flow between agents.

### Follow-up 2

Add a Board tab to the dashboard that summarizes the drafted messages and what has happened with each open ticket.

**What was missing in the original prompt:** The original asked for a per-run summary of what each agent did, but not for a separate, persistent view of all drafted messages and each ticket's overall progress across runs.

### Follow-up 3

Keep the header fixed while scrolling so the checking balance is always visible. (The same message asked for worker-to-worker hand-offs on the web and less revealing customer drafts; those are logged under Problem 5, Follow-up 1.)

**What was missing in the original prompt:** The original asked to show the checking balance but not that it stay visible at all times while scrolling.

# Problem 9: Resolve the tickets

## Initial prompt (verbatim)

Problem 9: Resolve the tickets

Step 0) btw, a resolved run could be that we drafted a message to the customer clearly saying when something can b done, or can't be done. 
Step 1) before we start testing the agents on a full run over the three tickets, let's reset the working database data/campus_customs_new.db so we can start fresh
Step 2) run all three tickets on the board (101, 102, and 103) until each is resolved
Step 3) Open the output/desk_tickets.html file and update the "actual" sections that we had left blank earlier. Update them with what actually happened. We can compare that to what I had earlier for expected (do not edit those)
Step 4) On the cash tab of that same html, itemize the money (starting balance, how cash changed when each ticket was resolved and how/why), and then the ending checking balance (which must match the cash_accounts in the working database)
Step 5) Save output/resolved_tickets.json: for each ticket have the id, final status, short outcome, what each agent contributed, and if there were any human approvals. also save output/resolved_board.html which is a page we can doubleclick to open which has a screenshot of oyr react board for all 3 resolved ticket (101, 102, 103)
Step 6) make sure you are appending to the audit trail json (no overwriting) and finish harness.md so it covers all the tables, tools, agents, API routes, the dashboad, and the safety ruls. Make sure it is clear so that a manager can read through it and it all makes sense.

## Summarized follow-up prompts

### Follow-up 1

During the full run, asked where to click Approve. Claude isn't permitted to approve payments itself, so the human must approve each request on the board.

**What was missing in the original prompt:** "Run until each is resolved" didn't say that the human would need to be present to click Approve on each payment and purchase-order request during the run.

### Follow-up 2

Confirmed that the pending payments (invoice 501 and rent) were approved on the board, so the run can continue with the follow-ups and ticket 103.

**What was missing in the original prompt:** Nothing new; this is the human-approval step the run depends on.

### Follow-up 3

Human decisions on the purchase orders: approved #3 (1 tee size S, $8, ticket 101) and denied #4 (12 hoodies size M, $264, ticket 103, more than the $160 in checking). Continue the follow-ups so 101 and 103 resolve.

**What was missing in the original prompt:** The original didn't say which restock purchases to fund when cash couldn't cover all of them; the human made that call during the run.

# Problem 10: Reflection

## Initial prompt (verbatim)

Problem 10: Reflection

Step 1) open desk_tickets html to the reflections tab
Step 2) the questions I will answer: (1) how would i evaluate the performance of the agents on each ticket and why? (2) for each ticket, how did the actual compare to the expected? (3) what would have been simpler with 1 agent with tools (and why)? (4) describe  3 new problems campus customs might face and be able to overcome with these agents and tools, (5) describe 3 new problems the agents would face and could not overcome and why and explain the tools i would need to overcome them.
Step 3) Answers (these are rough so please expound on them and add color to my words): (1) ticket one was good, it realized that we needed to pay an open invoice first before we could commit to sending a new one to the customer. The customer service agent's email is not a great email for a customer to receive (such as explaining that we need to pay our own invoices first). I had the agent updated after i noticed that so now it is better. For the rent one, it was pretty straight forward. However, we did not necessarily need a email drafted for that one. For the last one,  it was a little more complicated but at least we were able to tell the customer no. It did not even touch on the bulk discount though which I think is an omission. Also, each agent called the tools many times. I don't know if it could have been more efficient and called it fewer times (2) for the first ticket, I was correct that the inventory would get called first and the accounting, but there were way more calls than expected. The same is true for each ticket. I got it right wit hthe second one as well it being facilities + accounting, for the 3rd ticket customer service was called on as well which I didn't include. And way more tools were called for all 3. (3) the facilities agent could just have been lumped in with accounting in my opinion. (4) these agents would be good at solving (a) a customer asking how much an item cost, (b) determining our margins, (c) letting customers know how many items are left of a different sku. (5) these agents would not be good at: (a) making decisions on bulk discounts and pricing strategies, (b) telling customers what a similar item is (that is not a different size) that would help them get somethung different but similar, and c) these agents would not be good at telling someone how far their item is if a customer already placed an order and is wondering where it is. It would need tools that connect to when something was placed, and determine updated lead time from there or tools to compare items or tools that maximize profits given margins. 
Step 4) tie all of my answers above to each ticket and this app and expound on what I have written above as my answers to those 5 questionbs. you can use the ticket tabs and cash tabs as evidence. The evidence/write up should tie specifically to the Campus Customs, just like I have it written above in my own words

## Summarized follow-up prompts

### Follow-up 1

(Background, from before this prompt.) An earlier one-line version of Problem 10 ("open the desk_tickets html and now we will fill out the reflection section") was sent while Problem 9 was still running and then withdrawn. This full prompt replaced it.

**What was missing in the original prompt:** The earlier version had no questions, no draft answers, and no instruction to back them with evidence from the ticket and Cash tabs.

# Problem 11: Submit to Github

## Initial prompt (verbatim)

[Image attached: a screenshot of the expected folder layout. It shows `hw5/` containing `AI_prompts.md`, `requirements.txt`, `.env.example`, `.gitignore`, `.mcp.json`, `README.md`, `data/` (`campus_customs.db`, `campus_customs_new.db`), `mcp_server/` (`server.py`, `README.md`), `frontend/`, `backend/` (`main.py`, `models.py`, `prompts/` with `boss.md`, `inventory.md`, `accounting.md`, `facilities.md`, `customer_service.md`), and `output/` (`harness.md`, `mcp_smoke.json`, `desk_tickets.html`, `design.md`, `resolved_tickets.json`, `resolved_board.html`, `audit_trail.json`, `github_url.txt`).]

Problem 11: Submit to Github

Step 1) Above is a screenshot of what the file layout should look like. Check nothing is missing and make sure it follows the above structure. 
Step 2) push the code to my public GitHub repo and give me the repo link so i can copy it and share it with the graders of the assignment
Step 3) do not share my real .env to the github repo but DO include both database files under data/ (the original and the working copy) so that the graders can run my app easily
Step 4) the README should explain: copy original db to the working copy when you need a clean run, start MCP server, start FastAPI backend, start the react board, reset the db before a full 3 ticket run.

## Summarized follow-up prompts

_No follow-up prompts yet._

_What was missing in the original prompt: Nothing identified yet; follow-up prompts have not been provided._

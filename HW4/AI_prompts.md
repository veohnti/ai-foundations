# HW4 — AI Prompt Log

# Problem 1: Vibe Coder Prompts

## Initial prompt (verbatim)

Problem 1: Vibe Coder Prompts

I already used the skill when setting up the environment. In the ai_prompts.md file, log this prompt as you usually would. However, for this question only, also include my prompt history within this folder. Moving on to the next problems, we will resume the typical usage of our skill

## Prompt history in this folder (included at the user's request, for Problem 1 only)

These are the user's earlier messages in the HW4 folder, before Problem 1 was stated. They were originally treated as tooling setup rather than assignment prompts, and so were not logged; they are reproduced here because this problem asked for the folder's prompt history.

1. `/folder-workspace` — "in HW4 please"
   - Invoked the folder-workspace skill, naming HW4 as the workspace for the request.
   - Result: HW4 established as the working folder; `joke.txt` created there as the skill's proof file.

2. `/ai-prompt-tracker` — (no arguments)
   - Invoked the ai-prompt-tracker skill for this assignment.
   - Result: `AI_prompts.md` created in HW4 as an empty scaffold, with no problem sections, since no assignment prompt had been given yet.

## Summarized follow-up prompts

_No follow-up prompts yet._

_What was missing in the original prompt: Nothing identified yet; follow-up prompts have not been provided._

---

# Problem 2: Analyze the database

## Initial prompt (verbatim)

Problem 2: Analyze the database

Step 1) unzip the data file in there for me please
Step 2) read through the db file (data/campus_customs.db) to familiarize yourself with it (you should at least understand catalogue, inventory, and users)
Step 3) We will now begin building the harness.md, which we will continue to build over the next couple of problems. For now, please include each table and its field, a short sentence on why each field is relevant to the shop or to the chatbot. Later on, we will add models, tools, safety etc... to the file

## Summarized follow-up prompts

_No follow-up prompts yet._

_What was missing in the original prompt: Nothing identified yet; follow-up prompts have not been provided._

---

# Problem 3: Build the Campus Customs Website

## Initial prompt (verbatim)

Problem 3: Build the Campus Customs Website

Step 1) Scaffold React, Vite, and Typescripts front end for Campus Customs
Step 2) I want a navigation bar at the top that links to the following: Home, Products, About Us, Log In, and Create Account
Step 3) For the home and about us sections, you can take inspiration from the yalebulldogblue.com website but not verbatim. Please use my voice instead. For example for About US: "Founded in [...] we do [...] mainly for [this type of apparel]". Make it not too professional or businessy and a little bit fun.
Step 4) On the Products page, have icons of product images from the catalogue (the image paths are in the data base). When you click on one, I would like it to open a single item page where the left side has an enlarged picture of the product, and on the right side it has the description of the product, sizes available, price, etcc (whatever is available for that product which would be relevant to display). Clicking the icon / card of the product should take the shopper there.
Step 5) On the bottom right of the page, please add a chat interface (it can be a floating chat panel) . In this problem, we don't need for it to be connected to an agent yet (we will likely build that later) For now it can be a stub that will call our backend later
Step 6) Start a simple FastAPI App in backend/main.py to just serve product and images. Later on, we will grow this into the agent backend. We are doing this because soon we will need an API to read the database

## Summarized follow-up prompts

### Follow-up 1

Liked the site, but said it was hard to read. Asked to restyle it using swatch
Combination 6 from the Sanzo Wada *Dictionary of Color Combinations*
(sanzo-wada.dmbk.io) and to make the page more readable overall.

**What was missing in the original prompt:** The original prompt specified the pages,
layout, and voice but never named a color palette or set any readability bar, so the
build fell back to the project's default black-and-green theme with small, low-contrast
secondary text. The follow-up supplied the palette (Grenadine Pink + Deep Indigo) and
made legibility an explicit requirement.

### Follow-up 2

Corrected the palette: the swatch meant by "collection 6" was not Grenadine Pink and
Deep Indigo but the six colors shown in an attached screenshot — White #ffffff,
Neutral Gray #b5d1cc, Mineral Gray #9fc2b2, Warm Gray #9cb29e, Slate Color #1b3644,
and Black #000000. Asked for the site to be redesigned around those, and for a link to
view the result.

**What was missing in the original prompt:** Follow-up 1 named the palette only by
source and number, and the numbering on that site addresses two different things — the
book's color *combinations* and its swatch *collections*. Combination 6 was pulled when
Swatch Collection 6 was meant. The screenshot removed the ambiguity by giving the hex
values directly. The request for a link also showed that "done" means a running URL to
look at, not just changed files.

### Follow-up 3

Reported that the link no longer worked, and asked for the background to be white
because the black one was hard to read.

**What was missing in the original prompt:** Two gaps. First, nothing in the earlier
prompts said the site had to stay reachable between sessions — the dev servers were
started for a one-time demo and died when the machine slept, so the URL handed over in
Follow-up 2 was only good while that session lasted. Second, "readable" had been treated
as a contrast problem and solved inside a dark theme; the real preference was a light
page, which the palette's White and Slate values support directly.


---

# Problem 4: Create Account & Login

## Initial prompt (verbatim)

Problem 4: Create Account & Login

Step 1) Please create a typical log-in/create account structure. For the create account: email field, first name field, last name field, create password field, confirm password field. For the log in: email field and password field.
Step 2) Please store every new account in the "users" table. Please ensure that the passwords are stored securely so that AI and humans can't hack it!
Step 3) You'll find a test username (ie email) and password in the seed database. You can use that to test while building. (it's test@campuscustoms.yale.edu and the password is password)
Step 4) confirm that you can log in as that user. Also confirm that the workflow works when you create a new account
Step 5) update the harness.md file to explain how the authentication process you build works

## Summarized follow-up prompts

_No follow-up prompts yet._

_What was missing in the original prompt: Nothing identified yet; follow-up prompts have not been provided._

---

# Problem 5: PydanticAI Agent Backend

## Initial prompt (verbatim)

Problem 5: PydanticAI Agent Backend
Goal of this problem is to build the agent that we will use for our chatbot.
Step 1) create the chatbot agent using the FastAPI (PydanticAI Agent), plugged into the frontend chatbot you build for the webpage
Step 2) Place the API in backend/main.py (this is the file we run with uvicorn)
Step 3) Keep the agent as the following 4 files next to it: backend/prompts/prompt.md (this will be the system prompt which we will grow later), backend/agent.py (agent wiring/entry), backend/tools.py (tools the agent will call, as you could guess), backend/models.py (pydanticAI agent)
Step 4) in main.py expose the chat route so a message from the website returns a reply from the agent (and whatever else we'd need for products/auth)
Step 5) Use my PORTKEY API KEY. And you can use gpt 5.6 terra
Step 6) in prompts/prompt.md, put safety basics and campus custom's voice. We will expand on this later
Step 7) update or create types in models.py for chat replies and product cards as needed. 
Step 8) in harness.md (in the output), note how the front end talks to the FastAPI and how the agent is loaded 
Step 9) ensure the backend  runs from backend/ folder like below: uvicorn main:app --reload --port 8000

## Summarized follow-up prompts

### Follow-up 1

Reported that chat answers showed raw markdown like `**Fencing Left Chest Hoodie**`
(literal asterisks) instead of styled text, and asked to fix the formatting.

**What was missing in the original prompt:** The agent was specified to return markdown
in its `reply`, but nothing said how the chat panel should render it. The panel printed
the string verbatim, so markdown syntax leaked to the shopper. The fix was to render the
reply as markdown in the bubble (added `react-markdown` plus bubble styling), which the
original build should have accounted for once the reply format was markdown.

### Follow-up 2

Reported that after the markdown fix the user's own question no longer appeared in the
chat (the dark user bubble rendered empty), and asked to fix that plus anything else
wrong in the screenshot.

**What was missing in the original prompt:** Two rendering gaps exposed by switching the
bubble to markdown. First, the global `p { color: var(--slate) }` rule won over the user
bubble's white text (markdown wraps text in `<p>`, so slate text landed on the slate
bubble and was invisible); fixed by forcing `.bubble-text` descendants to inherit the
bubble's color. Second, when the model returned a "loose" markdown list (blank lines
between items) react-markdown wrapped each item in a `<p>`, whose block margins opened a
large gap inside the bubble; fixed by zeroing `.bubble-text li p` margins and tightening
list spacing. Neither was specified because the switch to markdown rendering was itself a
follow-up, so its interaction with the existing theme rules had not been accounted for.

---

# Problem 6: Tools: product info and stock

## Initial prompt (verbatim)

Problem 6: Tools: product info and stock
The goal of this problem is to give our agent some tools
Step 1) give the agent tools to lookup information from campus_customs.db
Step 2) The information we are looking for is: product description, price, and how many are in stock (if the customer asks, it should have this by size as well)
Step 3) The agent should not invent anything and only refer to the database. If something is out of stock, say so.
Step 4) In prompts/prompt.md, add to that file so the agent knows to call these specific tools for questions related to price or stock. 
Step 5) Add/update anything related to return types  in model.py
STep 6) in our harness file, please list every tool  and explain which model fields was chosen to lookup results, and explain why.
Step 7) earlier we switched to opus 4.8 for some reason. is it possible to switch back to opus 5.5? I want to make sure my assignment turns out really good (opus 5.5 on medium). But if that means you have to rerun everything, then dont do it. Only if now moving forward we could switch back

## Summarized follow-up prompts

### Follow-up 1

Reported that the site link no longer worked and asked for it again.

**What was missing in the original prompt:** Nothing about the tools themselves — the
dev servers had been stopped when the previous session ended, so the URL had nothing
behind it. The recurring gap is that no prompt has asked for the app to stay running
between sessions; the servers are restarted on demand, and the run commands in
README.md let the site be brought back without help.

---

# Problem 7: Chat search that updates the page

## Initial prompt (verbatim)

Problem 7: Chat search that updates the page

Step 1) We are adding a new feature! When a customer asks about a certain type/category of product, not only do you provide results in the chatbox, but I would like the webpage to update as well so it is only showing the associated results. This works kind of like a filter. So if someone asks "What kind of crewnecks do you have?" the page refreshes with that information in tiles (as product cards)
Step 2) Essentially, the agent returns structured product matches and the front end updates it on the website. This should be an API contract.
Step 3) Make sure the functionalities of the webpage/chatbot still work from problem 3 (where we get a details page if you click on an image with all the product info). I checked and it seemed to work but also do a quick check
Step 4) update prompts/prompt.md and output/harness.md so it is clear to a hypothetical manager how the search results reach the page

## Summarized follow-up prompts

_No follow-up prompts yet._

_What was missing in the original prompt: Nothing identified yet; follow-up prompts have not been provided._

---

# Problem 8: Customer Memory

## Initial prompt (verbatim)

Problem 8: Customer Memory

Step 1) Save chat history for customers when they are logged in. To do this, the agent should be able to save the history in an apropriate database, and when the customer logs back on, it can re-read that history so it is up to date
Step 2) The chatbox should know their name and email. So they can answer like: "here, Veohnti". You can put that in the agent's deps and/or tools that the agent can call.
Step 3) no need to save down chats for users who are not logged in
Step 4) When a user is chatting to the bot, and they have a product on the page, or a filtered view on the page, the agent should have enough page context so that if the user says " do you have this in another color" the agent know what the user is referring to. (to achieve this, you can place the code in the agent's context)
Step 5) in harness.md, document how chat history is stored, what customer fields the agent sees, and how it achieve's page context

## Summarized follow-up prompts

### Follow-up 1

Asked to reconnect the host, because the site link had stopped working again.

**What was missing in the original prompt:** Nothing in the memory feature itself.
The dev servers had stopped when the session ended, so the link had nothing behind
it. Same recurring gap as Problem 6, Follow-up 1: no prompt asks for the app to stay
running between sessions, so it is restarted on request (run commands are in
README.md).

---

# Problem 9: Usability Improvements

## Initial prompt (verbatim)

Problem 9: Usability Improvements

Step 1) Add two front-end improvements: (a) the ability for customers to compare two products side by side. When you click on a product, you have the ability to click a button that allows you to choose another item that you can select and then you can compare the two items side by side. (b) the second front-end improvement would be twofold: there are clothing pictures with black backgrounds (see picture) which does not look nice. Please change those pictures so they have black backgrounds. The second part is to add a carousel of apparel on the home page. We also need more pictures/visuals on the website. 
Step 2) Add 2 back-end agents: (a) ranking suggestions in the chatbot based on customer questions. (b) asking clarifying questions to help the search
Step 3) Create output/usability.md. For each improvement (front end and back end) include 1) why I added it, and 2) why it helps campus customs be a better business and how it helps the shopper. 
Step 4) Make sure the improvements work

## Summarized follow-up prompts

### Follow-up 1

Reported still seeing black backgrounds and no moving carousel, asked for a quick fix
(and less time spent), and said to drop the background work if it was hard and
focus on the carousel.

**What was missing in the original prompt:** Nothing about the features themselves.
The photos had been replaced on the server, but browsers kept their cached copies
because the file names were unchanged, so image URLs now carry a version tag
(`?v=white-bg-1`). The carousel paused itself when the system's "reduce motion"
setting was on. It now always advances, switching instantly instead of sliding in
that case. The prompt also gave no time budget; the follow-up asked for faster
turnaround.

### Follow-up 2

Asked to replace the top-left hero image (the jagged navy Basic Hoodie) and said the
carousel still wasn't visible.

**What was missing in the original prompt:** The prompt asked for a home-page carousel
but not where on the page. It sat below a full-height hero, so on a typical screen it
was off-screen. The hero is now shorter, so the carousel starts on the first screen,
and its images load up front instead of lazily. The top-left hero photo is now the
Champion Reverse Weave hoodie, which was shot on white originally and has clean edges.


---

# Problem 10: Style the website

## Initial prompt (verbatim)

Problem 10: Style the website

Step 1) come up with a Logo that has two overlapping Cs. Use that logo on the website.
Step 2) update the palette with the 4 colors i shared in the picture. Please make it so there is more color pop on the website
Step 3) font: please use the same font as Loewe (or something very similar)
Step 4) Add the two images I have of models wearing Yale shirts to the website so they are located on the website in a stylish way (maybe side by side and like the Loewe example I have up?)
Step 5) I will have to share this website as an html ultimatly to TAs, can you make sure you save the image references if necessary for them to see it if they were to click an html file to see my website?
Step 6) create output/design.md where you explained what we changed and why it would make the customer stay on the website to shoo.

## Summarized follow-up prompts

### Follow-up 1

Asked for the home-page carousel to move a little faster.

**What was missing in the original prompt:** No speed was set for the carousel in
Problem 9 or here, so it used a cautious 4.5 seconds per card. It now advances
every 2.8 seconds with a quicker 0.4-second slide, in both the live site and the
offline copy.

---

# Problem 11: Site testing (app check)

## Initial prompt (verbatim)

Problem 11: Site testing (app check)

Step 1) test the live app and document it in: output/app_check.html (this should be a page you can double click to open)
Step 2) Include screenshots and captions for: (1) chat checking inventory level (no making up numbers, it should all be from the db), (2) the dynamic asearch result cards which appear after you ask for something in the chat, and (3) the compare feature we added in problem 9
Step 4) We want the html to be easy to grade for our teaching assistants: heading for each check, screenshot, and 1-2 sentencs of what the screenshot proves. 
Step 5) put the screenshots in output/app_check_images/ and link them from app_check.html with relative paths (for example: app_check_images/compare.png)

## Summarized follow-up prompts

_No follow-up prompts yet._

_What was missing in the original prompt: Nothing identified yet; follow-up prompts have not been provided._

---

# Problem 12: Audit Trail, safety, finish harness

## Initial prompt (verbatim)

Problem 12: Audit Trail, safety, finish harness

Step 1) maintain an append only (NO OVERWRITE) output/audit_trail.json of agent activity loops (time, tool name, short args/result, stop reason). SINCE IT IS APPEND ONLY, MAKE SURE IT DOES NOT WIPE BETWEEN RUNS. 
Step 2) add some safety rules to give the agent and add them to prompts/prompt.md (such as never asking sensitive information and never making up information)
Step 3) Now we finish output/harness.md so a manager can read it and it is clear to them how the system works. We need: model fields in models.py and why they were chosen, every tool and their abilities, safety rules, and specs (loop limits, result caps, models, how to run front and back end)
Step 4) that is all we'll be adding to harness so make sure it reads like a finished document

## Summarized follow-up prompts

_No follow-up prompts yet._

_What was missing in the original prompt: Nothing identified yet; follow-up prompts have not been provided._

---

# Problem 13: Push to Github and submit the URL

## Initial prompt (verbatim)

Problem 13: Push to Github and submit the URL

Step 1) the expected file layout should be like the layout I shared in the picture
Step 2) put the code in the folder named HW4 
Step 3) do not put the real env. , campus_customs.db, or product images  in the Github repo. We will use gitignore. include env.example with placeholders only
Step 4) the agent itself should be 4 files under backend/: prompts/prompt.md, agent.py, tools.py, and models.py
Step 5) README.md should explain how  tto run the front end and back end after placing the data pack
Step 6) since you are connected to github, can you please push it to the public github repo. and give the URL when you are done so i can submit it as my assignment

## Summarized follow-up prompts

_No follow-up prompts yet._

_What was missing in the original prompt: Nothing identified yet; follow-up prompts have not been provided._

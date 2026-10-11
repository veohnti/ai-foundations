# Campus Customs Agent Desk — Design

The dashboard (`frontend/`, React + TypeScript + Vite) looks like a bold, typed shop ledger: a white page carrying heavy ink-outlined boxes, solid colored shadows, and vivid color from the inspiration photo. Delegation between agents is drawn as a live, glowing web.

## Color palette

### Palette strip (from the inspiration image)

Each color is the average of its swatch.

| Name | RGB | Where it's used | Why |
|---|---|---|---|
| Royal blue | `rgb(34, 44, 131)` | Masthead band, panel title bars, the Boss's card, selected ticket, "Complete" stamp, cash total | The anchor color: authority, identity, and anything final or trusted (money, completed work). A full-width royal band at the top immediately breaks up the white. |
| Coral | `rgb(238, 89, 99)` | Primary buttons, ticket number blocks, "Needs approval" stamps, the approval panel and callout when something waits on you, the Accounting agent's color, "Saying" labels | The call-to-action color: whatever needs you right now. |
| Peach | `rgb(242, 179, 167)` | Title lettering on the royal band, the default offset shadow on panels, the soft wash behind selected tickets and agents' spoken lines | Warmth and depth. It gives every box a printed, lifted look without fighting the louder colors. |
| Silver | `rgb(179, 179, 179)` | Idle ticket shadows, dashed table rules | Quiet structure, like the silver vases in the photo. Only for inactive or secondary things. |

### Vivid accents (taken from the photo itself)

| Name | RGB | From the photo | Where it's used | Why |
|---|---|---|---|---|
| Cobalt | `rgb(46, 76, 222)` | The blue glass | The Inventory agent, "Doing" labels, MCP tool chips, the "Open" stamp, the web panel's shadow | The palette strip alone read flat. The photo's brightest blue adds the vibrancy you asked for. |
| Rose | `rgb(214, 51, 108)` | The ranunculus | The Facilities agent, "Agents working" stamp, cash drop (−$840.00), refusals | A hot pink between coral and royal, for "live" and "changed" moments. |
| Violet | `rgb(124, 77, 196)` | The sweet peas | The Customer Service agent, "Thinking" labels, run summary frame, customer drafts | Completes a five-color set so every agent has a distinct color. |
| Night | `rgb(20, 26, 84)` | A deeper royal | Team web background | A dark stage, so the hand-off lines can actually glow. |

### One color per agent

Each agent keeps the same color everywhere: its card header and shadow, its node in the web, every hand-off line it sends, and the "Asked" label on a teammate's card.

| Agent | Color |
|---|---|
| Boss | Royal `rgb(34, 44, 131)` (glows as periwinkle `rgb(150, 165, 255)` inside the dark web so it stays visible) |
| Inventory | Cobalt `rgb(46, 76, 222)` |
| Accounting | Coral `rgb(238, 89, 99)` |
| Facilities | Rose `rgb(214, 51, 108)` |
| Customer Service | Violet `rgb(124, 77, 196)` |

- **Text:** ink `rgb(26, 28, 58)`, with secondary text in `rgb(88, 90, 120)`.
- **Page:** white `rgb(255, 255, 255)`.

**Why one color per agent:** it lets you follow who is talking to whom at a glance, across the web, the cards, and the summary.

## Typography

| Use | Font | Why |
|---|---|---|
| Display: title, panel bars, agent names, stamps, the THINKING / DOING / SAYING labels | **Special Elite** | A worn, inked typewriter face that matches the "PERFECT THOUGHTS" sample. |
| Body: feeds, tickets, tables, buttons | **Courier Prime** | A typewriter monospace drawn for screens. Same voice, but readable in long feeds and dollar amounts. |

- **Bundled fonts:** both are self-hosted through `@fontsource`.
- **Title:** the masthead's `[C|A|M|P|U|S]` echoes the boxed letters in the "PERFECT" sample.

## Boxes

- **Outline:** every box has a 3px ink outline and a solid, unblurred offset shadow in a palette color, like a stamped card.
- **Color bars:** panel titles sit on solid color bars (royal by default, coral when your approval is needed, violet for the summary).
- **Agent cards:** each has a full-color header in that agent's color. Its shadow turns full-strength and the card lifts while the agent works.

**Why:** you said the first draft's boxes faded into the page. Heavy outlines and solid shadows make each box read as a distinct object on white, and colored headers carry color into every section.

## Layout

1. **Masthead (fixed):**
   - A full-width royal band with peach typewriter lettering, the shop date, and the **checking card** (with the change shown after an approval).
   - A **Reset** button.
   - Underneath, a seven-color **palette strip** echoing the inspiration image.
   - **Fixed to the top:** it stays put as you scroll. After you scroll, it shrinks (smaller title, slimmer cash card, no subtitle) so it takes less room but the **checking balance is always visible**. **Why:** you want to watch cash at all times, especially when approving.
2. **Left column (sticky):**
   - **Tickets:** each card has a colored number block (coral; royal when selected; violet when complete) and a rubber-stamp status.
   - **Your approval:** below the tickets. It turns coral, gently nudges, and shows a count badge when something waits on you. Approve & pay and Deny are right there.
3. **Main column:**
   - **Ticket header:** subject, details, status stamp, and one clear run button. It reads Start the agent team, Team at work…, Waiting on your approval, Continue with the team, or Run the team again.
   - **Team web** (see below).
   - **Agent cards:** the Boss full width, then the four specialists (two across, or one when narrow). Each card has a live feed: **ASKED** (in the asking agent's color), **THINKING**, **DOING**, and **SAYING**.
   - **Run summary:** after the run: the boss's final call, then one row per agent with what it did, its drafts (marked *not sent*), and the MCP tools it used.

## Board tab

A second tab next to **Agent desk**. Its badge shows how many messages have been drafted. It reads the shop's board (`GET /board`), so it reflects everything since the last reset, not just one run.

| Part | What it shows | Style |
|---|---|---|
| Stat boxes | Open tickets · drafted messages (never sent) · amount waiting on you · checking | Thick boxes with a colored top bar and shadow (royal, violet, coral when something is pending, cobalt) |
| One card per open ticket | **Where it stands:** the boss's latest decision note | Royal-washed block with a royal edge |
| | **What happened:** a timeline of status changes with times | Peach rail with coral dots |
| | **Money:** each payment or purchase order with its amount and status (paid · approved by …, pending, denied) | Royal when paid, coral when pending |
| | **Drafted messages:** newest first. The newest is open and tagged *Latest*; older ones collapse to one line (click to expand). Each shows who it's to, who drafted it, "not sent", and a **Copy text** button | Violet panel; each draft edged in the drafting agent's color |
| Completed tickets | The same cards, collapsed under one heading | Violet ID block, silver shadow |

**Why:** the agent desk shows one run as it happens. The Board answers "where does everything stand, and what's ready to send?" in one place. Drafts are grouped by ticket, newest on top, so you read the current message first. **Open in agent desk →** on each card, and the ticket list on the left, jump straight back to that ticket's live view.

## Team web (delegation)

The five agents are nodes on a dark royal stage: the Boss on top, the four specialists around it. Faint dotted strands connect **every pair**, showing that any agent can reach any other.

| What you see | Meaning |
|---|---|
| A thick line in the **sender's color**, glowing, with dashes **flowing toward** the teammate and an arrowhead | A hand-off is in progress. It stays lit while the teammate works. |
| A short bright streak racing **back** along the line in the teammate's color | The teammate just reported back. |
| A thinner solid line with an arrowhead | A finished hand-off. The history stays visible. |
| A node filled with color, with a pulsing ring | That agent is working right now. |
| A node with a check badge | That agent is done. |

- **Right now:** a line under the web, edged in the sender's color, reads, for example, "Boss → Accounting" with the exact task.
- **Hand-off chips:** numbered and colored (for example "① Boss → Inventory · reported back ✓"), with the full task and answer on hover.
- **Clicking a node:** scrolls to that agent's card.
- **Specialist ↔ specialist:** the same glowing lines, chips, and "Right now" line show specialists consulting each other (for example *Customer Service → Inventory*, *Facilities → Accounting*), drawn in the asking specialist's color.

**Why:** you asked to see delegation clearly. Direction is shown by both the flowing dashes and the arrowhead. Color tells you who sent it. The chips give the exact order, so you can follow the chain without reading the feeds.

## Motion

| Animation | Where | Why |
|---|---|---|
| Flowing dashes and a glow halo | Live hand-off lines | Show direction and "happening now" |
| Report-back streak | Runs once along the line, in reverse | Shows the answer coming back |
| Pulsing ring, dot, and blinking caret | Working agents | Show who is busy |
| Typed-in fade | New feed lines | Feel like text being typed |
| Lift and colored shadow | Working agent card, cash card after a payment | Draw the eye to what just changed |
| Gentle nudge | Approval panel when something waits on you | Make the human step hard to miss |
| Key press | Buttons push into their ink shadow | Typewriter-key feel |

**Why:** every animation marks something live or just changed, so the motion carries meaning instead of decoration.

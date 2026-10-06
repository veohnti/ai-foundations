# Campus Customs: Usability Improvements

Five improvements for Problem 9: three on the front end and two back-end agents.
Each section covers what the improvement is, **why I added it**, and **why it makes
Campus Customs a better business and how it helps the shopper**. Each ends with how
it was checked.

| # | Improvement | Where |
|---|---|---|
| 1 | Compare two products side by side | Front end |
| 2 | White backgrounds on every product photo | Front end (images) |
| 3 | Home-page carousel and more visuals across the site | Front end |
| 4 | Ranking agent for recommendations | Back end |
| 5 | Clarifying-question agent | Back end |

---

## 1. Compare two products side by side

**What it is.** Every product page now has a **"⇄ Compare with another item"**
button. It opens a searchable picker of the whole catalogue (minus the item you're
on). Pick one and you land on a compare page with the two products side by side:
- **Photos and names** of both, each linking to its product page.
- **A row-by-row table:** price (the cheaper one is tagged "Lower price"), garment
  type, colors (colors both share are highlighted), stock for every size (sold-out
  sizes are struck through), total units, and the full description.
- **"Change item" and "Swap sides"** buttons, so you can keep comparing without
  starting over.

The chat assistant also knows both products on screen, so "which of these is
warmer?" gets a straight answer.

**Why I added it.** Most of our catalogue comes in close pairs: a Saybrook crewneck
vs. a Saybrook quarter-zip, a hoodie vs. a fleece at a different price. Shoppers
were stuck bouncing between two product pages trying to remember which had their
size in stock. I wanted the decision to happen on one screen.

**Why it helps Campus Customs and the shopper.**
- **For the shopper:** it answers "which one should I get?" in one look. Price,
  colors, and live stock per size line up, so they don't buy the one that turns
  out not to have their size. The "Lower price" tag and shared-color highlight do
  the comparing for them.
- **For the business:** shoppers who can't decide between two items often leave
  and decide "later." Comparing keeps them on the site and moves them to a
  purchase. Comparing a $68 hoodie with a $98 fleece also shows what the extra $30
  buys, which can lift order value honestly rather than through pushy upselling.
  Because stock comes live from the database, we never sell a comparison on
  sizes we don't have.

**How it was checked.** Basic Hoodie Big Yale → Compare → the picker opened with 101
items (the hoodie itself was excluded). Searching "saybrook fleece" narrowed it to one
item, and picking it loaded `/compare/basic-hoodie-big-yale/saybrook-sweater-fleece-jacket`.
The table showed $68 (tagged "Lower price") vs $98, per-size stock (the fleece's XXL
shown as sold out, matching the database), and 60 vs 31 units in total. In the chat on
that page, "which of these is warmer, and which is cheaper?" got: the fleece is warmer,
and the hoodie is $30 cheaper.

---

## 2. White backgrounds on every product photo

**What it is.** 74 of our 102 product photos had black backgrounds. Some were
garments cut out on solid black; others were white photos padded with black bars
at the sides. All 74 now sit on white, matching the site's white cards. A script
(`scripts/whiten_backgrounds.py`) did it, and the originals are kept untouched in
`data/products_original/`, so it can be re-run or undone.

The careful part was not damaging the clothes, because most of these garments are
**navy**:
- **What counts as background:** the script only turns pixels white that are pure
  black, neutral (navy fabric keeps a blue tint, even in shadow), and connected to
  the image edge.
- **Thin gaps:** the fill can't squeeze through a hairline gap into the garment.
- **Arm gaps:** the black showing between an arm and the body gets cleared too.
  Dark hood linings near the top of the photo are kept, because they're real
  fabric.
- **Edges:** the dark fringe and specks along each outline are blended into white,
  so the clothes don't look cut out with scissors.
- **Checked by eye:** every one of the 74 results was reviewed on contact sheets,
  and the trickiest ones were zoomed in against the originals.

**Why I added it.** About three-quarters of the product grid was black squares next
to white ones. It looked messy and dated, made the navy clothing hard to see, and
fought the site's light design. A clean, consistent catalogue is the first thing a
shopper notices.

**Why it helps Campus Customs and the shopper.**
- **For the shopper:** navy hoodies, our biggest category, were nearly invisible on
  black. On white, the shape, logo, and color of each piece are easy to read, so
  they can tell items apart and know what they're buying.
- **For the business:** consistent, professional product photos make a small shop
  look trustworthy, and trust is what turns a browser into a buyer. It also means
  the photos work everywhere the site now uses them (carousel, category tiles,
  compare page, chat cards) without black boxes breaking the layout. The edit is
  scripted and reversible, so new products with black backgrounds can be processed
  the same way.

**How it was checked.** A check on the live site loaded all 102 served images and
found **0** with a dark border (previously 74). All 74 processed photos were reviewed
on contact sheets. Close-up comparisons confirmed the navy garments kept their full
outline and the hood linings stayed dark.

---

## 3. Home-page carousel and more visuals across the site

**What it is.**
- **"Fresh off the rack" carousel** on the home page: 12 hand-picked products
  covering every garment type, colleges, sports, The Game, and the family pieces.
  It slides one card at a time and loops. It pauses when you hover or tab into it,
  and has arrows and position dots. It doesn't move on its own for visitors whose
  system is set to reduce motion.
- **Hero photo collage:** four product photos beside the home-page headline,
  instead of text alone.
- **"Shop by category" tiles:** Crewnecks, Hoodies, T-shirts, Zips & jackets, each
  with a photo. A tile opens the Products page already filtered to that category
  (`/products?category=hood`).
- **Family band:** the Mom / Dad / Grandpa / Aunt pieces shown with photos next to
  the "Fits for every kind of Yalie" copy.
- **About page photo strip:** five product photos under the headline.

**Why I added it.** The home page was all text: a headline, four text cards, and a
paragraph. For a clothing shop that undersold the product. People shop apparel
with their eyes, and nothing on the first screen showed what we actually sell.

**Why it helps Campus Customs and the shopper.**
- **For the shopper:**
  - **Instant picture:** the first screen now shows what the shop carries.
  - **Hands-free browsing:** the carousel shows a spread of the range without
    them doing anything.
  - **Fewer steps:** category tiles get them to "just the hoodies" in one click
    instead of two.
  - **Accessibility:** pause-on-focus, keyboard-reachable controls, and the
    reduced-motion setting keep the carousel friendly for people with motion
    sensitivity or no mouse.
- **For the business:** a visual home page lowers the share of visitors who leave
  without clicking anything. Every carousel card, tile, and photo is a link
  straight to a product or category, so there are more paths to a product page
  and more chances to sell. The featured list is ours to curate: it can push The
  Game merch in November or family gifts before parents' weekend.

**How it was checked.** The home page rendered the 4-photo collage, 12 carousel slides
(9 positions at 4 per view), 4 category tiles, and 4 family tiles. The carousel
auto-advanced on its own, and the previous/next arrows and dots each moved it to the
expected position. Clicking the Hoodies tile opened `/products?category=hood` with the
dropdown set to Hoodies and all 27 hoodies showing.

---

## 4. Ranking agent for recommendations

**What it is.** A separate back-end AI agent (in `backend/agent.py`, with its own
section of `prompts/prompt.md`). The shop assistant calls it, through the `rank_suggestions`
tool, when a shopper asks for a **recommendation** ("what's the warmest thing under
$100?", "a hoodie for a gift"). The backend pulls matching, in-stock candidates
from the database with their descriptions, colors, prices, and sizes, and the
ranker orders them for the shopper's need. It gives each a one-line reason drawn
only from the product data. The chat shows the top picks in that order, each card
with its reason.

There are safeguards in code, not just in the prompt:
- **No made-up products:** the ranker can only return products it was given; any
  other id is dropped.
- **No made-up details:** cards are rebuilt from the database, so names, prices,
  and stock are always real.
- **A fair candidate pool:** the pool is a balanced spread across categories, not
  just the cheapest items. An early version handed it only $32 tees, so it named
  a t-shirt "the warmest thing under $100." That was caught in testing and fixed.

**Why I added it.** Before this, "what's the best…" questions got whatever the plain
search returned first, which is the cheapest matches. That doesn't answer
"best for what?". I wanted recommendations that weigh what the shopper actually
said (warmth, occasion, recipient, size) and explain themselves.

**Why it helps Campus Customs and the shopper.**
- **For the shopper:** they get a short, ordered list of a few products that fit
  the request, each with a plain reason ("Full-zip sweater fleece; medium is in
  stock"). That replaces scrolling through 102 items, and the reasons show it
  isn't a random pick. Size-aware ranking means the top pick is one they can
  actually buy.
- **For the business:** good recommendations are how a small shop competes with a
  big one. A shopper who gets the right item quickly is more likely to buy and
  come back. Because the ranker only sees in-stock products and real data, it
  never recommends something we can't sell or describes a product falsely, which
  protects the shop's reputation for honesty.

**How it was checked.**
- **Warmth:** "What's the warmest thing you have under $100? I wear a medium"
  returned three full-zip fleece jackets, each $98. Medium is in stock on all
  three, which matches the database.
- **Gifts:** after the shopper tapped "A hoodie" in the gift flow, it returned
  three ranked hoodies with reasons, and every stock claim matched the database.

---

## 5. Clarifying-question agent

**What it is.** A second back-end agent (also in `backend/agent.py`, with its own
section of `prompts/prompt.md`). The shop assistant
calls it, through the `ask_clarifying_question` tool, when a request is too broad
to search well ("I need a gift", "what should I get?"). The backend gives it facts
about what the catalogue actually has for the request: how many products match,
counts per category, the most common colors, and the price points. It decides
whether one question would help. If so, it writes the question and 2–4 short
answers, and the chat shows those answers as **tappable buttons**. Tapping one sends
that answer, and the shopper gets results.

Rules that keep it from becoming annoying:
- **One question at most, and never twice in a row.**
- **Specific requests don't get questioned:** "show me crewnecks" or "the warmest
  thing under $100" goes straight to results.
- **Options must exist:** every option must be something the shop actually carries.
- **The question and buttons always match:** the shopper sees the agent's question
  word for word, so it always lines up with its buttons.

**Why I added it.** Broad requests like "I need a gift" match the whole catalogue.
The assistant either dumped a long list or guessed (it once just recommended three
tees). A good salesperson would ask one quick question first. I wanted the bot to
do the same, and to make answering it a single tap.

**Why it helps Campus Customs and the shopper.**
- **For the shopper:** one tap ("A hoodie") turns a vague wish into a focused set of
  recommendations, with nothing to type and no wading through 102 items. Because
  the options come from real catalogue facts, every button leads to results.
- **For the business:** it captures shoppers who don't know what they want yet,
  often gift buyers (parents, relatives) who are a big part of college-apparel
  sales. Better-targeted results mean fewer abandoned chats. The answers also show
  what kinds of products people reach for when they're unsure, which is useful for
  deciding what to stock and feature.

**How it was checked.**
- **Broad requests:** "I need a gift", "what should I get?", and "I want something
  nice for my roommate" each got one question that names its own options (for
  example "a hoodie, a crewneck, a t-shirt, or a quarter-zip?"), with matching
  buttons.
- **Specific requests:** "What kind of crewnecks do you have?" and the "warmest
  under $100" question got no clarifying question.
- **In the browser:** tapping the "A hoodie" button returned three ranked hoodie
  picks with reasons, and the buttons disappeared once answered.

---

## Bugs found and fixed while testing

Testing the improvements end to end turned up four problems, all fixed before
finishing:

- **Ranker saw only cheap items.** Its candidates were the 25 cheapest products,
  so for "warmest under $100" it saw only tees. Now it gets a balanced spread
  across categories.
- **Need words broke the clarifier.** The assistant passed need-words like "gift"
  as a text search, which matched nothing, so the clarifier saw an empty
  catalogue. Both tools now explain the difference, and fall back to the rest of
  the catalogue if a text filter matches nothing.
- **Runaway chat turn.** A turn in the browser hit the request cap of 10 and
  failed with a friendly error. The likely cause was the assistant writing out
  full product cards (names, prices, image URLs) that then had to validate. It
  now returns only product ids, the backend builds the cards, and turns use about
  3 model calls.
- **Question and buttons didn't match.** The clarifying question and its buttons
  disagreed ("cozy or everyday?" above garment-type buttons). The agent now writes
  the options first and names them in the question, and the backend shows its
  question word for word.

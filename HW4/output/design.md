# Campus Customs: Website Design (Problem 10)

What changed in the site's look, and why each change keeps a shopper on the site
long enough to buy.

## 1. Logo: two overlapping Cs

**What changed.** A new mark: two interlocking C's (one for Campus, one for
Customs). The first is Eosine Pink and the second Diamine Green. They're drawn so
the overlap darkens toward black, so the mark uses all four brand colors. It sits
in the nav next to the wordmark "Campus *Customs*" (serif, "Customs" in green
italic), and it's the browser-tab icon. It's an inline SVG, so it's sharp at any
size and works in the offline copy (`frontend/src/components/Logo.tsx`).

**Why it keeps shoppers here.** A real mark makes a small shop look established
and trustworthy, like a brand rather than a student project, and trust is what
turns browsing into buying. The tab icon helps a shopper find the site again among
their open tabs and come back to finish an order.

## 2. Palette: Sanzo Wada combination 242

**What changed.** The four colors from the page you shared ("Eosine Pink",
combination 242 in *A Dictionary of Color Combinations*), taken as published:

| Color | Hex | Where it's used |
|---|---|---|
| Eosine Pink | `#f37f94` | "Create Account" button, wordmark, nav underline, carousel dots, shared-color chips, hover states |
| Burnt Sienna | `#ae5224` | every price, the chat button, the "New Haven · Est. 2024" tag |
| Diamine Green | `#1a7444` | section labels, "Lower price" badges, the shopper's chat bubbles, button hovers |
| Black | `#111314` | text, primary buttons, the active nav item, chat header |

The page itself stays white (your earlier request for readability), and the colors
come in as **pops**. Each "Shop by category" tile gets its own color band (green,
sienna, black, pink), and section headings carry a short pink underline. Every
text and background pairing was checked for contrast: the lowest is 5.2:1 (white
on sienna), and all of them are above the 4.5:1 readability standard.

**Why it keeps shoppers here.**
- **Easier to scan:** color tells the eye where to go. Prices are always sienna,
  so they're easy to scan. The main actions are black or pink, so they stand out.
- **Feels like a brand:** a confident, distinctive palette makes the site feel
  designed. A memorable look is part of why someone returns to a shop rather
  than to a generic store.
- **Pops, not a wash:** keeping the background white means the colors read as
  highlights, so the product photos stay the focus.

## 3. Font: a Loewe look-alike

**What changed.** Loewe uses custom typefaces that aren't available to license,
so the site pairs two free, close matches:
- **Playfair Display** (a high-contrast serif, like Loewe's wordmark) for the
  logo, headlines, and section titles.
- **Hanken Grotesk** (a clean grotesk, like Loewe's navigation) for menus,
  buttons, prices, and body text.

Both are bundled from npm (`@fontsource`) instead of loaded from Google, so they
also show correctly in the offline copy.

**Why it keeps shoppers here.** The serif and grotesk pairing is what
fashion-house sites use. It makes the store feel premium and editorial, which
supports the price points and makes browsing feel like looking through a
lookbook. The grotesk keeps menus, prices, and sizes easy to read.

## 4. Editorial banner with the model photos (Loewe-style)

**What changed.** The home page now opens like Loewe's:
- **Photos:** your two model photos side by side across the full width of the
  window, split by a thin white line.
- **Wordmark:** an oversized "Campus *Customs*" in pink and green overlaps the
  top-left corner, like the LOEWE wordmark.
- **Tag:** a sienna "New Haven · Est. 2024" tag in the corner.
- **Motion:** a slow zoom when you hover over the photos.
- **Headline:** the headline and the "Shop the catalogue" buttons sit in a strip
  right under the photos, not on top of them, so the Yale sweatshirts stay fully
  visible.

The "Fresh off the rack" carousel follows immediately and now advances every
2.8 seconds.

**Why it keeps shoppers here.**
- **People wearing it:** product shots on their own show a garment, but photos of
  people wearing it show how it fits and how it feels to own. That is the strongest
  pull on an apparel site. Smiling models in the actual crest sweatshirts put the
  product in a real context within the first second.
- **A large, confident first screen:** it says "brand", which makes visitors more
  likely to scroll than bounce. The headline and buttons sit right under the
  photos, and the carousel comes next, so there's always an obvious next click.

## 5. A copy of the site your TAs can open as a file

**What changed.** `output/website/` is a self-contained copy of the site:
- **`index.html`:** the whole app in one file, with the code, styles, both fonts,
  the logo, and both model photos inlined.
- **`images/`:** the 102 product photos, referenced with relative paths.
- **Opening it:** double-click `index.html` and it opens straight from the file,
  with no server, internet, or setup.
- **What works:** browsing, search and filters, product pages, compare, and the
  carousel all work, using a snapshot of the catalogue and stock taken at build
  time.
- **What doesn't:** the AI shop assistant and log-in need the live backend, so
  in this copy they show a short note that they're off.

To rebuild it after changes: `.venv/bin/python scripts/export_static_site.py`
(from `HW4/`). This was checked by opening the file in Chrome: the home page,
the products grid with all images, and a compare page all rendered.

**Why it matters.** Anyone grading or reviewing the site sees exactly what a
shopper sees, with nothing to install and nothing that can break because a server
isn't running.

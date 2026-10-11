# The town: an ai-town style expo floor where sponsors sell tool seeds

## Problem

The plaza strip shows speakers talking, but there is nothing to walk into and nothing to do. The request:
an [ai-town](https://github.com/a16z-infra/ai-town) style world you can walk around in, rooms with a
screen for the presentations, and sponsor companies that sell tool seeds. The rooms may stay closed for
now; selling the seeds is the focus.

## What a tool seed is

The idea for an agent harness tool (a skill, hook or check) written down before its code: the problem,
when it fires, the mechanism and what it gates on. The nine seeds come from the author's wiki
(`work/seeds/*.md`), copied into `src/orgestra/resources/sponsors.toml`. Each seed's `grown_into` is the
product name and its `description` the pitch.

## Design

- **A page of its own, `/town`.** A full-width pixel world under the app bar. The home page links to it
  ("Visit the expo"). The page is not boosted in and out, so the three.js strip is not on it and comes
  back on the next page.
- **ai-town's look, our own art.** Top-down 16 px tiles drawn at an integer scale, characters with four
  facing directions and a two-step walk, speech bubbles. ai-town's sprite sheet has no credited source
  and its tileset is CC-BY-SA/GPL, so the art is drawn in code (`frontend/src/town/art.ts`) and no
  image is vendored. ai-town itself runs on Convex and an LLM; we keep our server-decided conversations.
- **The map** is an ASCII grid (`frontend/src/town/map.ts`): an expo hall with an entrance at the
  bottom, four sponsor booths on the floor and three presentation rooms along the top. Each room has a
  screen showing its next talk (the first with slides) and a rope across its door: walking into the
  rope or clicking the room's sign opens a panel that names the room's talks (with links) and says the
  doors open soon.
- **You walk.** Arrow keys or WASD, or click a tile to walk there (breadth-first path on the grid). The
  camera follows you. Signs over the booths and rooms walk you there when clicked; for the keyboard, the
  Directory beside the world lists every booth and room as a link that does the same.
- **Townsfolk.** Up to 10 speakers stroll the floor. The `/conversations/stream` turns make the speaker
  walk to the listener and show a bubble, as on the plaza. Booth staff call out a seed's one-line hook
  when you come near.
- **Booths sell.** A booth's panel is an htmx fragment, `GET /town/booths/<slug>`: the sponsor, its
  tagline and its seeds as products (name, price in expo coins, pitch, and Problem / When it fires /
  Mechanism / Gates behind a disclosure). "Add to bag" puts a seed in your bag. A place opens its panel
  only where you stop, not when you walk past it.
- **The bag** (bottom right) holds seed slugs in `localStorage`; everything else is derived: coins left
  (100 to start, minus the total), the total, and the stand deals. Taking every seed of one sponsor
  prices that stand at its bundle price (80% of the sum, rounded down), and the bag nudges you when one
  seed would complete a stand ("Add Stacked Reviews to complete Pipeline Pals and save 8"). You cannot
  buy past your coins; the button says how many you are short. The bag shows what the deals saved.
  Checkout shows a receipt with what each seed grew into; nothing is sent anywhere.
- **Reduced motion:** townsfolk stand still and nobody talks; you still move, one tile per key press.

## Data flow

`sponsors.toml` -> `orgestra.town.expo.load_expo()` (pydantic, at startup) -> `/town` embeds the
booth and room layout as JSON (slugs, names, colours, prices, bundle prices) and the cast; booth panels
come from `/town/booths/<slug>`, room panels from `/town/rooms/<n>`. Unknown slugs are 404.

## Testing

- pytest: the TOML loads and every seed belongs to a sponsor; `/town` renders with the town data;
  booth and room fragments; 404s.
- vitest: path finding (walls, ropes, unreachable), map parsing (every booth and room in the data has a
  place), bag pricing (bundle, nudge, budget).

## Out of scope

Opening the rooms and showing decks on the screens, LLM-driven townsfolk, replacing the plaza strip on
the other pages, real payment.

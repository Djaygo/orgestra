# Orgestra redesign: still Google, but worth coming back to

## Goal

Rebuild the whole interface so it keeps the Google look (white canvas, four-colour wordmark, pill
search box, blue as the one action colour) and stops feeling like a prototype. A visitor should be able
to find a talk in seconds, watch it, read its slides' matches, and join the discussion without friction,
on a phone as much as on a laptop, in light and in dark.

## What the audit found (before)

Captured with `npm run capture` (40 screenshots: 9 pages, phone and desktop, light and dark) and the
demo tour. Findings, worst first:

1. A 404 is raw JSON (`{"detail":"Talk not found"}`), with no site around it.
2. The talk page is a plain document: default bullet lists, default blue and purple links, half the
   screen empty, and no video player although the `video_url` of 26 talks is already an embed URL.
3. A permanent sidebar of 71 talks is the only navigation and dominates every page; on a phone it
   covers the whole screen.
4. Results show "Posts 0" and "Activity" for every talk, which is noise; there are no filters, no
   highlighted match terms, and the empty state is one line.
5. The fixed 3D stage covers the bottom quarter of every page, including text, and loads three.js on
   every page.
6. The home page is bare: a cut-off placeholder on phones, two misaligned buttons, nothing to try.
7. The visual system is ad hoc: Arial, hard-coded colours, no focus styles, no motion, no skip link.

## Decisions

- **Keep the identity, raise the craft.** Google blue as the single action colour, the wordmark, the
  pill search box, restrained surfaces. Material 3 conventions for shape, tone and state layers.
- **Self-hosted type.** Roboto (variable, latin) served from `/static/fonts`, never
  from a CDN. Material 3 type scale.
- **Design tokens.** One `tokens.css` of CSS custom properties: colour roles in `oklch()` using
  `light-dark()`, type scale, 4px spacing scale, radii, elevation, motion. Components use roles
  (`--surface`, `--on-surface-muted`, `--primary`), never raw colours.
- **Theme.** Follows the system; a toggle (light, dark, system) stores the choice in `localStorage` and
  is applied before first paint, so there is no flash.
- **Navigation without the sidebar.** A sticky top app bar: wordmark, search (hidden on the home page,
  where it is the hero), Browse, theme toggle, Report a bug. `/browse` lists every edition and the
  speakers, with a filter box. The sidebar is removed.
- **Search that helps.** Predictions while typing (talk titles, speakers, topics) in an accessible
  combobox; `/` and Ctrl or Cmd+K focus the box; filter chips (year, has slides, has video); matched
  words highlighted in snippets; a helpful empty state with topics to try.
- **Watch the talk on the talk page.** Embed the video for the two known hosts
  (`youtube-nocookie.com/embed`, `player.vimeo.com/video`), lazy-loaded; any other URL stays a link.
- **The plaza is a treat, not a tax.** The 3D stage is a fixed band on the home page only; elsewhere it
  is a band at the end of the page, and three.js loads only when it scrolls into view (it already does).
  Under `prefers-reduced-motion` it renders one still frame.
- **Motion with meaning.** View transitions between pages (through htmx), a short entrance for result
  cards, state-layer feedback on controls. Everything off under `prefers-reduced-motion`.
- **2026-ready CSS, no build step.** `light-dark()`, `color-mix()`, `oklch()`, container queries,
  `:has()`, `field-sizing`, `text-wrap: balance`, `@view-transition`. Plain CSS files linked from the
  base template. All of it is feature-guarded so older browsers fall back to a readable page.
- **Icons.** One inline SVG sprite (Lucide-style strokes), no emoji, always with a text label or an
  accessible name.
- **Accessibility is a requirement, not a polish pass:** 4.5:1 text contrast in both themes, visible
  focus, 44px touch targets on phones (24px minimum on desktop), a skip link, labelled controls,
  `aria-live` for result updates, reduced motion, no information by colour alone.

## Pages

### Shell

Top app bar: wordmark (link home), search pill (on every page but home), Browse, theme toggle (icon
button with a label), Report a bug (shown when the feature is on). `main` has one `h1` per page. A
"Skip to content" link is the first focusable element. On phones the bar is two rows: wordmark and
actions, then the search pill.

### Home

Wordmark, search pill with predictions, then a row of two buttons: "I'm feeling curious" (tonal) and
"Browse talks" (outlined). Under them "Try:" with the six most common tags as chips. A quiet line:
edition names, number of talks, speakers, talks with slides, talks with video, and the hint "Press / to
search". The plaza stage is a fixed band at the bottom.

### Results

A summary line ("6 talks for automation"), filter chips (Any year, 2026, 2025; Slides; Video) that
are links so they work without JavaScript and survive reload, then result cards. A card: speaker
avatars and names with the year and track, the title, a snippet with highlighted words, and a meta row:
video and slides indicators, the slide the match is on ("Slide 25"), posts when there are any, tags,
and why-it-matched badges with score tooltips. "People also ask" stays as an expandable card after the
second result. No results: an illustration, "Nothing matched <query>", topic chips and a Browse link.
While a live search is running the list dims and has `aria-busy`.

### Talk

Breadcrumb (Browse, year, track), title, speaker chips, when and where, tags. Main column: the video
player (when embeddable), the abstract (readable measure), "Questions this talk answers", Related
talks, Discussion. Aside (wide screens; below the abstract on phones): Slides button with the page
count, Schedule link, Share (copy link with a toast), more by the speakers. A talk without details says
so kindly and links to the schedule.

### Speaker

Header card (large avatar, name, role, bio), link chips (website, profiles, email when public), the
talks as cards.

### Browse

Year tabs and a Speakers tab, a filter box (client-side), each talk a compact row with indicators.

### Report a bug and errors

The form as a card with visible labels, helper text and character counters, a friendly confirmation. A
branded error page for 404 and 500 (HTML for browsers, the existing JSON for API clients) with a search
box and topic chips.

### Discussion

A composer card that expands when focused, a clean thread with indentation guides and collapsible
replies, text-button actions, the existing edit and history, kind badges, the same data and routes.

## Behaviour that needs code

- Filters: `year`, `slides=1`, `video=1` on `/search`; chip counts come from the unfiltered hits.
- `highlight(text, words)` filter: escapes, then wraps whole-word matches in `<mark>`.
- `/suggest?q=`: up to 6 predictions, prefix matches first (titles, speakers, tags); fragment for htmx.
- `Talk.embed_url`: only the two known hosts, else `None`.
- `Catalog.related(talk, limit=3)`: extracted talks sharing the most tags (then speakers, then same
  year), never the talk itself; `Catalog.popular_tags(limit=6)`.
- `/browse`, `/browse?year=2026`.
- Error pages for 404 and 500 when the client accepts HTML.
- `ui.ts` (the only new script): theme, shortcuts, combobox keyboard handling, copy link, browse
  filter; each as a small pure function with tests.

## Testing and verification

- pytest for every behaviour above; vitest for the pure functions of `ui.ts`.
- `npm run capture` after the redesign shows every page in both sizes and both themes; reviewed
  page by page against the audit list.
- The demo tour is updated for the new markup and recorded; a before and after comparison video joins
  the recording of the old tour with the new one.
- Contrast of every colour role pair is checked by a script against the 4.5:1 and 3:1 thresholds.

## Out of scope

Changing the search ranking, the data, the discussion rules, accounts, a service worker or offline
mode, translations, and a CSS or JavaScript build pipeline beyond the existing Vite entry.

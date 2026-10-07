# Slide search and match badges

## Goal

Search also matches the text inside slide decks, and a result can point at the page where the match
is ("Slide 14"). Every result says why it matched: which fields contributed, and how much.

## Decisions

- **Decks are committed.** The 19 real slide decks are downloaded to `<year>/<slug>/slides.pdf` and
  committed with the data (about 240 MB; the owner chose this knowing it stays in history).
- **Text comes from the PDF's own text layer** (`pypdf`, permissive license; PyMuPDF is AGPL). No OCR:
  a deck without text is skipped and logged.
- **The app does not serve the PDFs.** A slide link goes to the original `slides_url` with `#page=N`.
- **Extraction happens at startup**, with a git-ignored per-deck cache keyed by the PDF's size and
  modification time, so only the first run is slow.
- **Placeholders are not slides.** The schedule extraction left `__PENDING__` in 12 talks'
  `slides_url`; the loader treats it as "no slides". That also removes a dead "Slides" link on the
  talk page and a wrong "slides" badge in the sidebar.

## Behaviour

### Data

- `scripts/fetch_slides.py <data-dir>` reads every `talk.json`, downloads each talk's real
  `slides_url` (http(s), not the placeholder) to `slides.pdf` next to it when the file is missing, and
  records `"slides_file": "slides.pdf"` in `talk.json`, in the year's `index.json` entry, and the
  edition's `slides_downloaded` count in the organization's `index.json`. Re-running changes nothing
  that is already downloaded. A response that is not a PDF (does not start with `%PDF`) is rejected
  and reported, and nothing is written for that talk.
- `data/**/slides.json` is a cache and is git-ignored.

### Reading the decks

- `slides.py` turns a PDF into `SlidePage(number, text)` records, one per page that has text (page
  numbers are 1-based and count every page).
- `load_pages(pdf)` returns the cached pages when `slides.json` next to the PDF matches the PDF's size
  and modification time (`st_size`, `st_mtime_ns`), otherwise it extracts, writes the cache and returns
  the pages. A PDF that cannot be read yields no pages, is logged with its path (not its content) and is
  cached as empty so it is not retried on every start.
- `load_slides(data_dir, catalog)` returns `{talk.ref: pages}` for every talk whose `slides_file` exists
  on disk, at `data_dir/<organization>/<year>/<slug>/<slides_file>`.

### Search

- `SearchIndex.build(catalog, thesaurus, slides=None)` takes those pages. Without them nothing changes.
- A talk's slide text is a new field, "slides". Its score for a variant is `SLIDES_WEIGHT` (0.4) times
  the number of pages the variant appears on, capped at `MAX_SLIDE_PAGES` (3). The deck adds at most
  `SLIDES_WEIGHT * MAX_SLIDE_PAGES` (1.2) to a talk's score in total, summed over every word of the
  query (the per-word scores are scaled down together), so a long deck cannot outrank a title match by
  repetition, not even the title match of a talk without details (3.0 * 0.5 = 1.5). Typo correction
  also knows the slide words. When two variants of a word score the same, the one that sorts first
  wins, so the badges do not change between starts.
- A hit remembers `slide_page`: the page that matches the most query concepts (ties: most occurrences,
  then the lowest page number), or `None` when no page matches.
- Ordering, coverage scaling and the unextracted-talk weight are unchanged.

### Match badges

- `Hit.matches` lists `FieldMatch(field, score)` for every field that contributed, best first: the sum
  of that field's score over all query concepts, using for each concept the variant that scored best.
- Labels: title "Title", tags "Tag", speakers "Speaker", questions "Question", abstract "Abstract",
  slides "Slides".
- Each result shows one badge per match. Hovering or focusing a badge shows a tooltip, "<label>: <score
  to one decimal>" (CSS tooltip from `data-tip`, so it also shows on keyboard focus). When the slides
  field matched and the talk has a real `slides_url`, its badge reads "Slide <page>" and links to
  `<slides_url>#page=<page>`.

## Components

| Unit | Responsibility | Depends on |
|---|---|---|
| `dataset.py` (`Talk.slides_url`) | placeholder becomes `None` | none |
| `slides.py` | `SlidePage`, `extract_pages`, `load_pages`, `load_slides` | `pypdf`, `Catalog` |
| `search.py` | slides field, page choice, per-field breakdown, `FieldMatch` | `slides.py` |
| `app.py` | loads slides at startup and passes them to the index | `slides.py`, `search.py` |
| `templates/partials/results.html`, `app.css` | badges, tooltip, slide link | `Hit` |
| `scripts/fetch_slides.py` | downloads decks, records them in the JSON | stdlib |
| `frontend/scripts/record-demo.mjs` | a zoomed tour of the new result badges | none |

## Testing

- `Talk`: `__PENDING__` and `None` both give no `slides_url`; a real URL is kept; the talk page and
  the sidebar show no slides link or badge for a placeholder.
- `slides.py` with a small PDF built in the test (the project has no PDF writer): pages with text are
  returned with their numbers, a blank page is skipped but still counted, the cache is written and then
  reused (a second call does not call `extract_pages`), a changed file is re-extracted, and an
  unreadable file gives no pages and does not raise, as does a data directory that cannot be written.
- Search: a word found only in a deck ranks that talk, reports the right `slide_page`, is capped at
  three pages, and keeps a title match above a deck-only match; `matches` names the contributing
  fields with scores that add up to the pre-scaling field total; without slides the results equal the
  results before this change.
- Templates: badges for each field, a "Slide N" link with the right `#page=N`, no slide link when the
  talk has no real URL.
- `fetch_slides.py` with an injected downloader (no network): downloads only missing decks, rejects a
  non-PDF response, never touches placeholders, updates `talk.json`, the year index and the edition
  count, and is idempotent.
- The demo gains a second tour, `--tour slides`, that zooms in on the new result badges.

## Out of scope

OCR, video transcripts, embeddings, serving the PDFs, per-slide result cards, re-ranking beyond the
capped slides field, and a progress indicator for the first extraction.

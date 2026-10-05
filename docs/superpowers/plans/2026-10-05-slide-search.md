# Slide Search and Match Badges Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Search matches the text inside slide decks and every result shows why it matched, with a "Slide N" link to the matching page.

**Architecture:** `slides.py` extracts page text from committed PDFs with `pypdf` and caches it per deck; `SearchIndex` gets a capped "slides" field, a per-field score breakdown and the best page per hit; the result template renders badges with CSS tooltips. `scripts/fetch_slides.py` downloads the decks and records them in the JSON.

**Tech Stack:** FastAPI, Jinja2, attrs, pypdf, rapidfuzz, pytest, ruff, ty, Playwright (demo).

**Spec:** `docs/superpowers/specs/2026-10-05-slide-search-design.md`

## Global Constraints

- Dependencies only through `uv add` (`pypdf`); never edit `pyproject.toml` by hand.
- Text comes from the PDF text layer only (`pypdf`); no OCR, no PyMuPDF (AGPL). The app never serves the PDFs; slide links go to `slides_url#page=N`.
- The 19 decks are committed as `slides.pdf` (the owner chose this knowing it adds about 240 MB to history); `data/**/slides.json` is a git-ignored cache.
- `slides_url` equal to `__PENDING__` means no slides everywhere.
- Slides score: `SLIDES_WEIGHT = 0.5` times pages matched, capped at `MAX_SLIDE_PAGES = 3`; ordering, coverage scaling and the unextracted-talk weight are otherwise unchanged; with no slides, results equal the old results.
- Line length 110; `uv run ruff check src tests scripts`, `uv run ruff format --check` and `uv run ty check` must pass (4 older ruff errors in `scripts/build_gotocph_dataset.py` are out of scope).
- Comments describe the current state only; never remove existing comments or docstrings; suppressions need an inline reason.
- Commits end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; plain imperative style; no amending, no force-push.

## Review Focus

- A damaged, empty or non-PDF `slides.pdf` must never crash startup or search; it yields no pages and is not retried on every start (Task 1).
- A changed PDF must never be served from a stale cache (Task 1).
- A long deck repeating a word must not outrank a talk whose title has the word (Task 2).
- The slide link and badges must only use the page number and the real `slides_url`, never slide text, and a talk without a real URL gets no slide link (Task 3).
- The fetch script must reject an HTML error page saved as a deck, never touch placeholders and be idempotent (Task 4).

## File Structure

| File | Responsibility |
|---|---|
| `src/orgestra/dataset.py` | placeholder `slides_url` becomes `None` |
| `src/orgestra/slides.py` | `SlidePage`, `extract_pages`, `load_pages`, `load_slides` |
| `src/orgestra/search.py` | slides field, `FieldMatch`, `Hit.matches`, `Hit.slide_page` |
| `src/orgestra/app.py` | load slides at startup, pass to the index |
| `src/orgestra/templates/partials/results.html`, `static/css/app.css` | badges, tooltip, slide link |
| `scripts/fetch_slides.py` | download decks, record them in the JSON |
| `tests/pdfs.py`, `tests/test_slides.py`, `tests/test_search.py`, `tests/test_slide_results.py`, `tests/test_fetch_slides.py` | tests |
| `frontend/scripts/record-demo.mjs`, `README.md`, `data/gotocph/README.md`, `.gitignore` | demo tour, docs, cache ignore |

---

### Task 1: Placeholder fix, `pypdf` and the slide reader

**Files:**
- Modify: `pyproject.toml`, `uv.lock` (through `uv`), `src/orgestra/dataset.py`, `.gitignore`
- Create: `src/orgestra/slides.py`, `tests/pdfs.py`
- Test: `tests/test_slides.py`, `tests/test_dataset.py` (extend if it exists, else create)

**Interfaces:**
- Produces: `SlidePage(number: int, text: str)` (frozen attrs), `extract_pages(pdf: Path) -> list[SlidePage]`, `load_pages(pdf: Path) -> list[SlidePage]`, `load_slides(data_dir: Path, catalog: Catalog) -> dict[str, list[SlidePage]]`; test helper `make_pdf(pages: list[str]) -> bytes`; `PENDING_SLIDES = "__PENDING__"` in `dataset.py`.

- [ ] **Step 1: Add the dependency and the cache ignore**

Run: `uv add pypdf && uv run python -c "import pypdf; print(pypdf.__version__)"`
Append to `.gitignore`: a `# Slide text cache` comment line and `data/**/slides.json`.

- [ ] **Step 2: The test PDF builder** `tests/pdfs.py`

```python
"""A minimal PDF writer for tests: one line of Helvetica text per page (an empty string is a blank page)."""

from __future__ import annotations


def make_pdf(pages: list[str]) -> bytes:
    count = len(pages)
    kids = " ".join(f"{4 + 2 * index} 0 R" for index in range(count))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {count} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for index, text in enumerate(pages):
        page = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {5 + 2 * index} 0 R "
            "/Resources << /Font << /F1 3 0 R >> >> >>"
        )
        objects.append(page.encode())
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 24 Tf 72 700 Td ({escaped}) Tj ET".encode() if text else b""
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
```

- [ ] **Step 3: Write the failing tests**

`tests/test_slides.py`:

```python
import json

import pytest

from orgestra import slides
from orgestra.slides import SlidePage, extract_pages, load_pages, load_slides
from tests.conftest import make_talk
from tests.pdfs import make_pdf


def test_pages_with_text_keep_their_page_numbers(tmp_path):
    pdf = tmp_path / "slides.pdf"
    pdf.write_bytes(make_pdf(["Hello (world)", "", "Third page"]))

    assert extract_pages(pdf) == [SlidePage(1, "Hello (world)"), SlidePage(3, "Third page")]


@pytest.fixture
def counted_extraction(monkeypatch):
    calls = []
    real = slides.extract_pages

    def counting(pdf):
        calls.append(pdf)
        return real(pdf)

    monkeypatch.setattr(slides, "extract_pages", counting)
    return calls


def test_the_cache_is_written_once_and_reused(tmp_path, counted_extraction):
    pdf = tmp_path / "slides.pdf"
    pdf.write_bytes(make_pdf(["One", "Two"]))

    first = load_pages(pdf)
    second = load_pages(pdf)

    assert first == second == [SlidePage(1, "One"), SlidePage(2, "Two")]
    assert len(counted_extraction) == 1
    assert json.loads((tmp_path / "slides.json").read_text())["pages"][0] == {"number": 1, "text": "One"}


def test_a_changed_deck_is_extracted_again(tmp_path, counted_extraction):
    pdf = tmp_path / "slides.pdf"
    pdf.write_bytes(make_pdf(["Old text"]))
    load_pages(pdf)

    pdf.write_bytes(make_pdf(["New text, a little longer"]))

    assert load_pages(pdf) == [SlidePage(1, "New text, a little longer")]
    assert len(counted_extraction) == 2


@pytest.mark.parametrize("content", [b"not a pdf at all", b"", b"%PDF-1.4\ngarbage"])
def test_an_unreadable_deck_gives_no_pages_and_is_not_retried(tmp_path, counted_extraction, content):
    pdf = tmp_path / "slides.pdf"
    pdf.write_bytes(content)

    assert load_pages(pdf) == []
    assert load_pages(pdf) == []
    assert len(counted_extraction) == 1


def test_a_corrupt_cache_is_ignored(tmp_path):
    pdf = tmp_path / "slides.pdf"
    pdf.write_bytes(make_pdf(["Fresh"]))
    (tmp_path / "slides.json").write_text("{not json")

    assert load_pages(pdf) == [SlidePage(1, "Fresh")]


def test_load_slides_reads_the_decks_the_catalog_points_at(tmp_path, catalog):
    with_deck = make_talk("with-deck", slides_file="slides.pdf", year=2025)
    missing_file = make_talk("missing-file", slides_file="slides.pdf", year=2025)
    no_slides = make_talk("no-slides", year=2025)
    folder = tmp_path / "conf" / "2025" / "with-deck"
    folder.mkdir(parents=True)
    (folder / "slides.pdf").write_bytes(make_pdf(["Deck text"]))
    talks = {talk.ref: talk for talk in (with_deck, missing_file, no_slides)}

    loaded = load_slides(tmp_path, type(catalog)(organizations=[], talks=talks, speakers={}))

    assert loaded == {with_deck.ref: [SlidePage(1, "Deck text")]}
```

Add to the dataset tests (create `tests/test_dataset.py` with a `make_talk` import if the file does not exist):

```python
@pytest.mark.parametrize(
    ("given", "expected"),
    [("__PENDING__", None), (None, None), ("https://x.test/a.pdf", "https://x.test/a.pdf")],
)
def test_a_pending_slides_placeholder_is_no_slides(given, expected):
    assert make_talk("t", slides_url=given).slides_url == expected
```

- [ ] **Step 4: Run to verify they fail**

Run: `uv run pytest tests/test_slides.py tests/test_dataset.py -q 2>&1 | tail -6`
Expected: FAIL (`orgestra.slides` missing; placeholder kept).

- [ ] **Step 5: Implement**

In `dataset.py` add, above `class Talk`, `PENDING_SLIDES = "__PENDING__"` and inside `Talk` (after `_formats_as_list`):

```python
    @field_validator("slides_url", mode="after")
    @classmethod
    def _no_placeholder(cls, value: str | None) -> str | None:
        """The schedule extraction left "__PENDING__" where no deck was uploaded yet."""
        return None if value == PENDING_SLIDES else value
```

`src/orgestra/slides.py`:

```python
"""The text of the slide decks, page by page, cached next to each PDF."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import attrs
from pypdf import PdfReader

from orgestra.dataset import Catalog

logger = logging.getLogger(__name__)
logging.getLogger("pypdf").setLevel(logging.ERROR)  # damaged decks make pypdf warn about every object
CACHE_NAME = "slides.json"


@attrs.frozen
class SlidePage:
    number: int  # 1-based; counts pages without text too
    text: str


def extract_pages(pdf: Path) -> list[SlidePage]:
    reader = PdfReader(pdf)
    pages = [
        SlidePage(number, (page.extract_text() or "").strip())
        for number, page in enumerate(reader.pages, start=1)
    ]
    return [page for page in pages if page.text]


def read_cache(cache: Path, key: dict[str, int]) -> list[SlidePage] | None:
    try:
        stored = json.loads(cache.read_text(encoding="utf-8"))
        if {"size": stored["size"], "mtime_ns": stored["mtime_ns"]} != key:
            return None
        return [SlidePage(page["number"], page["text"]) for page in stored["pages"]]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def load_pages(pdf: Path) -> list[SlidePage]:
    """The pages of a deck, from the cache when the PDF's size and modification time still match."""
    stat = pdf.stat()
    key = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    cache = pdf.with_name(CACHE_NAME)
    cached = read_cache(cache, key)
    if cached is not None:
        return cached
    try:
        pages = extract_pages(pdf)
    except Exception:  # noqa: BLE001 - pypdf raises many error types on damaged files
        logger.warning("could not read the slides at %s", pdf)
        pages = []
    cache.write_text(json.dumps({**key, "pages": [attrs.asdict(page) for page in pages]}), encoding="utf-8")
    return pages


def load_slides(data_dir: Path, catalog: Catalog) -> dict[str, list[SlidePage]]:
    """Pages per talk ref, for every talk whose deck is on disk."""
    slides: dict[str, list[SlidePage]] = {}
    for talk in catalog.talks.values():
        if not talk.slides_file:
            continue
        pdf = data_dir / talk.organization / str(talk.year) / talk.slug / talk.slides_file
        if pdf.exists():
            slides[talk.ref] = load_pages(pdf)
    return slides
```

- [ ] **Step 6: Run to verify they pass**

Run: `uv run pytest -q 2>&1 | tail -3 && uv run ruff check src tests --output-format concise && uv run ruff format --check | tail -1 && uv run ty check | tail -1`
Expected: all pass and clean. If `tests.conftest` / `tests.pdfs` imports fail, check that `tests/__init__.py` exists (it does) and fix the import style used by the other tests.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock .gitignore src/orgestra tests
git commit -m "Read slide decks page by page and treat the pending placeholder as no slides"
```

---

### Task 2: Search over slides with a per-field breakdown

**Files:**
- Modify: `src/orgestra/search.py`, `src/orgestra/app.py`
- Test: `tests/test_search.py`

**Interfaces:**
- Consumes: `SlidePage`, `load_slides` (Task 1).
- Produces: `FieldMatch(field: str, score: float)` with property `label: str`; `Hit.matches: list[FieldMatch]`; `Hit.slide_page: int | None`; `SearchIndex.build(catalog, thesaurus, slides: dict[str, list[SlidePage]] | None = None)`; constants `SLIDES_WEIGHT`, `MAX_SLIDE_PAGES`, `FIELD_LABELS`.

- [ ] **Step 1: Read the existing search tests**

Run: `sed -n 1,60p tests/test_search.py` and note how the index is built (`SearchIndex.build(catalog, thesaurus)` through fixtures) and how `Hit` is used.

- [ ] **Step 2: Write the failing tests** (append to `tests/test_search.py`, adapting the fixture names you saw)

```python
from orgestra.dataset import Catalog
from orgestra.slides import SlidePage


def index_with_slides(catalog, thesaurus, slides):
    return SearchIndex.build(catalog, thesaurus, slides)


def test_a_word_only_in_a_deck_finds_the_talk_and_the_page(catalog, thesaurus):
    slides = {
        "2025/llms-in-production": [SlidePage(1, "Welcome"), SlidePage(7, "Quokka routing in practice")]
    }

    hits = index_with_slides(catalog, thesaurus, slides).search("quokka").hits

    assert [hit.talk.slug for hit in hits] == ["llms-in-production"]
    assert hits[0].slide_page == 7
    assert [(m.field, m.label) for m in hits[0].matches] == [("slides", "Slides")]


def test_the_best_page_matches_the_most_concepts_then_the_most_words(catalog, thesaurus):
    slides = {
        "2025/llms-in-production": [
            SlidePage(2, "quokka"),
            SlidePage(5, "quokka wombat"),
            SlidePage(6, "quokka quokka wombat"),
        ]
    }

    hit = index_with_slides(catalog, thesaurus, slides).search("quokka wombat").hits[0]

    assert hit.slide_page == 6


def test_slide_repetition_is_capped_and_cannot_beat_a_title(catalog, thesaurus):
    many = [SlidePage(number, "kubernetes") for number in range(1, 40)]
    slides = {"2025/llms-in-production": many}
    index = index_with_slides(catalog, thesaurus, slides)

    hits = index.search("kubernetes").hits

    assert hits[0].talk.slug == "kubernetes-at-scale"
    deck_hit = next(hit for hit in hits if hit.talk.slug == "llms-in-production")
    assert deck_hit.matches[0].score == pytest.approx(SLIDES_WEIGHT * MAX_SLIDE_PAGES)


def test_matches_name_the_contributing_fields_best_first(catalog, thesaurus):
    hit = SearchIndex.build(catalog, thesaurus).search("kubernetes").hits[0]

    fields = [match.field for match in hit.matches]
    assert fields[0] == "title"
    assert set(fields) <= {"title", "tags", "speakers", "questions", "abstract"}
    assert [match.label for match in hit.matches][0] == "Title"
    assert all(match.score > 0 for match in hit.matches)
    assert hit.slide_page is None


def test_without_slides_the_results_are_unchanged(catalog, thesaurus):
    plain = SearchIndex.build(catalog, thesaurus)
    empty = SearchIndex.build(catalog, thesaurus, {})

    for query in ("kubernetes", "chatbot", "platforms"):
        assert [(h.talk.ref, h.score) for h in plain.search(query).hits] == [
            (h.talk.ref, h.score) for h in empty.search(query).hits
        ]
```
(import `SLIDES_WEIGHT`, `MAX_SLIDE_PAGES`, `SearchIndex`, `pytest` where the file does not already.) Remove the unused `Catalog` import if ruff flags it.

- [ ] **Step 3: Run to verify they fail**

Run: `uv run pytest tests/test_search.py -q 2>&1 | tail -6`
Expected: FAIL (`build()` takes no `slides`; `SLIDES_WEIGHT` missing).

- [ ] **Step 4: Implement in `search.py`**

Add imports `from collections import Counter` and `from orgestra.slides import SlidePage`. Add constants and types:

```python
SLIDES_WEIGHT = 0.5
# Pages a word is counted on, so a long deck cannot outrank a title match by repetition.
MAX_SLIDE_PAGES = 3
FIELD_LABELS = {
    "title": "Title",
    "tags": "Tag",
    "speakers": "Speaker",
    "questions": "Question",
    "abstract": "Abstract",
    "slides": "Slides",
}


@attrs.frozen
class PageTerms:
    number: int
    terms: Terms


@attrs.frozen
class FieldMatch:
    field: str
    score: float

    @property
    def label(self) -> str:
        return FIELD_LABELS[self.field]
```

`Document` gains `pages: list[PageTerms]`; `Hit` gains `matches: list[FieldMatch]` and `slide_page: int | None`. `document_for(talk, slides: list[SlidePage] = ())` builds `pages=[PageTerms(page.number, terms(page.text)) for page in slides]`. `SearchIndex.build(cls, catalog, thesaurus, slides=None)` uses `slides = slides or {}`, calls `document_for(talk, slides.get(talk.ref, []))` and adds the page terms to the vocabulary:

```python
        vocabulary = frozenset(t for doc in documents for field in doc.fields.values() for t in field) | frozenset(
            t for doc in documents for page in doc.pages for t in page.terms
        )
```

Replace `score_document` and `concept_score` with:

```python
def score_document(doc: Document, concepts: list[Concept]) -> Hit | None:
    """Sum of concept scores, scaled down by the share of concepts the talk does not match."""
    breakdowns = [concept_breakdown(doc, concept) for concept in concepts]
    scores = [sum(breakdown.values()) for breakdown in breakdowns]
    matched = sum(1 for score in scores if score > 0)
    if not matched:
        return None
    coverage = matched / len(concepts)
    weight = 1.0 if doc.talk.extracted else UNEXTRACTED_WEIGHT
    return Hit(
        talk=doc.talk,
        score=sum(scores) * coverage * coverage * weight,
        questions=matching_questions(doc, concepts),
        matches=field_matches(breakdowns),
        slide_page=best_slide_page(doc, concepts),
    )


def variant_scores(doc: Document, variant: Terms) -> dict[str, float]:
    scores = {name: weight * occurrences(variant, doc.fields[name]) for name, weight in FIELD_WEIGHTS.items()}
    pages = sum(1 for page in doc.pages if occurrences(variant, page.terms))
    scores["slides"] = SLIDES_WEIGHT * min(pages, MAX_SLIDE_PAGES)
    return scores


def concept_breakdown(doc: Document, concept: Concept) -> dict[str, float]:
    """Per-field scores of the concept's best-scoring variant (a synonym counts less than the typed word)."""
    typed = terms(concept.label)
    best: dict[str, float] = {}
    for variant in concept.variants:
        factor = 1.0 if variant == typed else SYNONYM_WEIGHT
        scores = {name: factor * score for name, score in variant_scores(doc, variant).items()}
        if sum(scores.values()) > sum(best.values()):
            best = scores
    return best


def field_matches(breakdowns: list[dict[str, float]]) -> list[FieldMatch]:
    totals: Counter[str] = Counter()
    for breakdown in breakdowns:
        totals.update(breakdown)
    ranked = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    return [FieldMatch(field, score) for field, score in ranked if score > 0]


def best_slide_page(doc: Document, concepts: list[Concept]) -> int | None:
    """The page matching the most concepts, then the most words, then the lowest number."""
    best: tuple[tuple[int, int, int], int] | None = None
    for page in doc.pages:
        counts = [
            sum(occurrences(variant, page.terms) for variant in concept.variants) for concept in concepts
        ]
        matched = sum(1 for count in counts if count)
        if not matched:
            continue
        rank = (matched, sum(counts), -page.number)
        if best is None or rank > best[0]:
            best = (rank, page.number)
    return best[1] if best else None
```
Delete the old `concept_score`. In `app.py`, import `from orgestra.slides import load_slides` and in `build_services` build the index with `SearchIndex.build(catalog, load_thesaurus(), load_slides(settings.data_dir, catalog))`.

- [ ] **Step 5: Run to verify they pass**

Run: `uv run pytest -q 2>&1 | tail -3 && uv run ruff check src tests --output-format concise && uv run ruff format --check | tail -1 && uv run ty check | tail -1`
Expected: all pass and clean. If an existing test constructed `Hit` or called `concept_score` directly, update it to the new signature without weakening it.

- [ ] **Step 6: Commit**

```bash
git add src tests
git commit -m "Search the text of slide decks and keep a per-field breakdown of each match"
```

---

### Task 3: Badges and the slide link in the result list

**Files:**
- Modify: `src/orgestra/templates/partials/results.html`, `src/orgestra/static/css/app.css`
- Test: `tests/test_slide_results.py`

**Interfaces:**
- Consumes: `Hit.matches`, `Hit.slide_page`, `FieldMatch.label` (Task 2); `make_pdf` (Task 1).

- [ ] **Step 1: Write the failing tests** `tests/test_slide_results.py`

```python
import json

import pytest
from fastapi.testclient import TestClient

from orgestra.app import Settings, create_app
from tests.pdfs import make_pdf

DECK_URL = "https://slides.example.com/deck.pdf"


def write_talk(root, slug, **fields):
    folder = root / "conf" / "2025" / slug
    folder.mkdir(parents=True)
    talk = {
        "slug": slug,
        "organization": "conf",
        "year": 2025,
        "session_id": abs(hash(slug)) % 10_000,
        "extracted": True,
        "title": slug.replace("-", " ").title(),
        "abstract": "A talk about something else.",
        "speakers": [],
        "session_url": f"https://example.com/{slug}",
    } | fields
    (folder / "talk.json").write_text(json.dumps(talk))
    return folder


@pytest.fixture
def client(tmp_path):
    root = tmp_path / "data"
    (root / "conf").mkdir(parents=True)
    index = {"slug": "conf", "name": "Conf", "url": "https://example.com", "editions": []}
    (root / "conf" / "index.json").write_text(json.dumps(index))
    deck = write_talk(root, "with-deck", slides_url=DECK_URL, slides_file="slides.pdf")
    (deck / "slides.pdf").write_bytes(make_pdf(["Welcome", "Zebra crossing patterns"]))
    write_talk(root, "placeholder-deck", slides_url="__PENDING__", title="Zebra Placeholder Talk")
    return TestClient(create_app(Settings(data_dir=root, db_path=tmp_path / "test.db")))


def test_the_slide_badge_links_to_the_matching_page(client):
    html = client.get("/search", params={"q": "zebra"}).text

    assert f'href="{DECK_URL}#page=2"' in html
    assert ">Slide 2<" in html
    assert 'data-tip="Slides: 0.5"' in html


def test_a_title_match_gets_a_plain_badge_with_its_score(client):
    html = client.get("/search", params={"q": "zebra"}).text

    assert 'class="match" tabindex="0" data-tip="Title: 3.0">Title<' in html


def test_a_talk_with_a_placeholder_has_no_slides_link_anywhere(client):
    results = client.get("/search", params={"q": "zebra"}).text
    talk = client.get("/talks/2025/placeholder-deck").text

    assert "__PENDING__" not in results
    assert "__PENDING__" not in talk
    assert ">Slides<" not in talk
    assert "slides</span>" not in talk
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_slide_results.py -q 2>&1 | tail -6`
Expected: FAIL (no badges in the results yet).

- [ ] **Step 3: Template and styles**

In `partials/results.html`, between the `hit-snippet` paragraph and the `{% if hit.talk.tags %}` block, add:

```jinja
        {% if hit.matches %}
          <p class="hit-matches" aria-label="Why this matched">
            {% for match in hit.matches %}
              {% if match.field == "slides" and hit.slide_page and hit.talk.slides_url %}
                <a class="match match-slides"
                   href="{{ hit.talk.slides_url }}#page={{ hit.slide_page }}"
                   rel="noopener"
                   data-tip="{{ match.label }}: {{ '%.1f'|format(match.score) }}">Slide {{ hit.slide_page }}</a>
              {% else %}
                <span class="match" tabindex="0" data-tip="{{ match.label }}: {{ '%.1f'|format(match.score) }}">{{ match.label }}</span>
              {% endif %}
            {% endfor %}
          </p>
        {% endif %}
```

Append to `app.css` before the first `@media` block:

```css
/* Why a result matched */
.hit-matches { margin: 0.35rem 0 0; }
.match {
  position: relative;
  display: inline-block;
  font-size: 12px;
  padding: 0 0.55rem;
  margin: 0 0.3rem 0.25rem 0;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--muted);
}
.match-slides { color: var(--link); }
.match-slides:hover { text-decoration: none; background: var(--hover); }
.match[data-tip]:hover::after, .match[data-tip]:focus::after {
  content: attr(data-tip);
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  z-index: 10;
  white-space: nowrap;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  background: var(--text);
  color: var(--bg);
  font-size: 11px;
}
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest -q 2>&1 | tail -3 && uv run ruff check src tests --output-format concise && uv run ruff format --check | tail -1 && uv run ty check | tail -1`
Expected: all pass. The first two assertions depend on the exact scores: the title score for a one-word title match is 3.0 and the slides score for one page is 0.5; if the formatting differs, fix the expectation only after confirming the arithmetic in `variant_scores`.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "Show why each result matched, with a link to the matching slide"
```

---

### Task 4: Fetch the decks and commit them with the data

**Files:**
- Create: `scripts/fetch_slides.py`
- Modify: `data/gotocph/**` (19 `slides.pdf`, the matching `talk.json`, year `index.json` and `index.json` entries)
- Test: `tests/test_fetch_slides.py`

**Interfaces:**
- Produces: `fetch_slides(data_dir: Path, fetch: Callable[[str], bytes] = http_fetch) -> Report`; `Report(downloaded: list[str], failed: list[str])`; `http_fetch(url: str) -> bytes`.

- [ ] **Step 1: Write the failing tests** `tests/test_fetch_slides.py`

```python
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from fetch_slides import fetch_slides  # noqa: E402 - needs the scripts directory on the path

PDF = b"%PDF-1.4\n%fake deck"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


@pytest.fixture
def data(tmp_path):
    org = tmp_path / "conf"
    write_json(
        org / "index.json", {"slug": "conf", "editions": [{"year": 2025, "talks": 3, "slides_downloaded": 0}]}
    )
    talks = {
        "real": "https://files.example.com/real.pdf",
        "html": "https://files.example.com/html.pdf",
        "pending": "__PENDING__",
    }
    entries = []
    for slug, url in talks.items():
        write_json(
            org / "2025" / slug / "talk.json",
            {"slug": slug, "year": 2025, "slides_url": url, "slides_file": None},
        )
        entries.append({"slug": slug, "slides_url": url, "slides_file": None})
    write_json(org / "2025" / "index.json", {"year": 2025, "talks": entries})
    return tmp_path


def downloader(responses):
    calls = []

    def fetch(url):
        calls.append(url)
        return responses[url]

    fetch.calls = calls
    return fetch


RESPONSES = {
    "https://files.example.com/real.pdf": PDF,
    "https://files.example.com/html.pdf": b"<html>404 not found</html>",
}


def test_downloads_real_decks_and_records_them(data):
    fetch = downloader(RESPONSES)

    report = fetch_slides(data, fetch)

    assert report.downloaded == ["2025/real"]
    assert [failure.split(":")[0] for failure in report.failed] == ["2025/html"]
    assert (data / "conf/2025/real/slides.pdf").read_bytes() == PDF
    assert not (data / "conf/2025/html/slides.pdf").exists()
    assert json.loads((data / "conf/2025/real/talk.json").read_text())["slides_file"] == "slides.pdf"
    assert json.loads((data / "conf/2025/html/talk.json").read_text())["slides_file"] is None
    entries = {e["slug"]: e for e in json.loads((data / "conf/2025/index.json").read_text())["talks"]}
    assert entries["real"]["slides_file"] == "slides.pdf"
    assert entries["html"]["slides_file"] is None
    edition = json.loads((data / "conf/index.json").read_text())["editions"][0]
    assert edition["slides_downloaded"] == 1
    assert "https://files.example.com/real.pdf" in fetch.calls
    assert "__PENDING__" not in fetch.calls


def test_running_again_downloads_only_what_is_missing(data):
    fetch_slides(data, downloader(RESPONSES))
    again = downloader(RESPONSES)

    report = fetch_slides(data, again)

    assert report.downloaded == []
    assert again.calls == ["https://files.example.com/html.pdf"]


def test_a_failing_download_is_reported_and_does_not_stop_the_rest(data):
    def broken(url):
        if "real" in url:
            raise OSError("connection reset")
        return b"%PDF-1.4 ok"

    report = fetch_slides(data, broken)

    assert report.downloaded == ["2025/html"]
    assert report.failed == ["2025/real: connection reset"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_fetch_slides.py -q 2>&1 | tail -4`
Expected: FAIL (`No module named 'fetch_slides'`).

- [ ] **Step 3: Implement `scripts/fetch_slides.py`**

```python
"""Download the slide decks listed in data/<organization>/<year>/<slug>/talk.json.

Each real `slides_url` (http or https, not the "__PENDING__" placeholder) is saved as `slides.pdf` next
to its talk.json and recorded as `"slides_file"` in talk.json, in the year's index.json and in the
edition's `slides_downloaded` count. Decks that are already downloaded are left alone, so re-running is
cheap, and a response that is not a PDF is reported and not saved.

Usage:
    python scripts/fetch_slides.py [data-dir]
"""

from __future__ import annotations

import json
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import attrs

PDF_MAGIC = b"%PDF"
DECK = "slides.pdf"
Record = dict[str, Any]


@attrs.frozen
class Report:
    downloaded: list[str]
    failed: list[str]


def http_fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "orgestra-dataset/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 - http(s) URLs from our dataset
        return response.read()


def read_json(path: Path) -> Record:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Record) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def record_deck(talk_path: Path) -> None:
    talk = read_json(talk_path)
    if talk.get("slides_file") != DECK:
        write_json(talk_path, talk | {"slides_file": DECK})


def refresh_indexes(organization_dir: Path) -> None:
    """Make the year indexes and the edition counts agree with the decks on disk."""
    organization_path = organization_dir / "index.json"
    organization = read_json(organization_path)
    for edition in organization.get("editions", []):
        year_path = organization_dir / str(edition["year"]) / "index.json"
        if not year_path.exists():
            continue
        year = read_json(year_path)
        for entry in year["talks"]:
            if (year_path.parent / entry["slug"] / DECK).exists():
                entry["slides_file"] = DECK
        edition["slides_downloaded"] = sum(1 for entry in year["talks"] if entry.get("slides_file"))
        write_json(year_path, year)
    write_json(organization_path, organization)


def fetch_slides(data_dir: Path, fetch: Callable[[str], bytes] = http_fetch) -> Report:
    downloaded: list[str] = []
    failed: list[str] = []
    for talk_path in sorted(data_dir.glob("*/*/*/talk.json")):
        talk = read_json(talk_path)
        url = talk.get("slides_url") or ""
        if not url.startswith(("http://", "https://")):
            continue
        deck = talk_path.with_name(DECK)
        ref = f"{talk['year']}/{talk['slug']}"
        if not deck.exists():
            try:
                data = fetch(url)
            except Exception as error:  # noqa: BLE001 - any failure of one deck must not stop the others
                failed.append(f"{ref}: {error}")
                continue
            if not data.startswith(PDF_MAGIC):
                failed.append(f"{ref}: not a PDF")
                continue
            deck.write_bytes(data)
            downloaded.append(ref)
        record_deck(talk_path)
    for organization_dir in sorted(path.parent for path in data_dir.glob("*/index.json")):
        refresh_indexes(organization_dir)
    return Report(downloaded=downloaded, failed=failed)


def main() -> None:
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "data"
    report = fetch_slides(data_dir)
    print(f"{len(report.downloaded)} downloaded")
    for failure in report.failed:
        print(f"  ! {failure}", file=sys.stderr)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_fetch_slides.py -q 2>&1 | tail -3 && uv run ruff check src tests scripts/fetch_slides.py --output-format concise && uv run ruff format --check | tail -1 && uv run ty check | tail -1`
Expected: 3 passed, clean.

- [ ] **Step 5: Commit the script**

```bash
git add scripts/fetch_slides.py tests/test_fetch_slides.py
git commit -m "Add a script that downloads the slide decks and records them in the data"
```

- [ ] **Step 6: Fetch the real decks and check the data**

Run: `uv run python scripts/fetch_slides.py data`
Expected: `19 downloaded` and no failures (network needed; if some fail, rerun once, then ledger the failures). Then `git status --short | rg -c slides.pdf` should be 19, `git diff --stat -- 'data/**/talk.json' | tail -1` shows 19 changed talk files, and `du -sh data/gotocph` is about 240 MB. Confirm `git check-ignore -v data/gotocph/2025/*/slides.json` reports the ignore rule once a deck cache exists.

- [ ] **Step 7: Commit the data**

```bash
git add data
git commit -m "Add the 19 slide decks of GOTO Copenhagen and record them in the data"
```

---

### Task 5: Demo tour, docs, real-data check and delivery

**Files:**
- Modify: `frontend/scripts/record-demo.mjs`, `README.md`, `data/gotocph/README.md`

**Interfaces:**
- Consumes: `.hit-matches`, `.match`, `.match-slides` with `data-tip` (Task 3); the committed decks (Task 4).

- [ ] **Step 1: Find a query that only the slides answer**

With the real data: start Python (`uv run python`), build the index (`from orgestra.app import Settings, build_services`; `services = build_services(Settings())`), print the time it took, then search a few distinctive words from the decks (for example take a rare word from `services.index.documents[...].pages`) until a query returns a hit whose `matches` has `slides` first and whose `slide_page` is set. Record that word as `SLIDES_QUERY`. Expected: first start extracts and caches every deck (note the seconds), the second start is near-instant.

- [ ] **Step 2: Add the zoomed tour to `record-demo.mjs`**

Add `tour: { type: "string", default: "full" }` to the options and change the `query` option to have no default; compute `const query = values.query ?? (values.tour === "slides" ? SLIDES_QUERY : "llm agnts");` (define `SLIDES_QUERY` from Step 1 as a constant with a one-line comment) and use `query` where `values.query` was used. Add:

```js
/** A close-up of the match badges: why each result matched and the slide the match is on. */
async function slidesTour(page) {
  await page.addInitScript(() => {
    document.addEventListener("DOMContentLoaded", () => {
      document.documentElement.style.zoom = "1.6";
    });
  });
  await page.goto(values.base);
  log("home");
  await pause(page, 1500);
  await page.locator("#q").pressSequentially(query, { delay: 110 });
  await page.keyboard.press("Enter");
  await page.waitForSelector(".hit-matches");
  log("results with badges");
  await pause(page, 3000);
  for (const badge of await page.locator(".hit-matches .match").all()) {
    await badge.hover();
    await pause(page, 1200);
  }
  const slide = page.locator(".match-slides").first();
  await slide.scrollIntoViewIfNeeded();
  await slide.hover();
  log("slide badge");
  await pause(page, 3000);
}
```
and make the recorder call `slidesTour(page)` when `values.tour === "slides"` instead of `tour(page)` (read how the existing code invokes `tour` and mirror it).

- [ ] **Step 3: Docs**

`README.md`: add a short paragraph after the search description: slide decks are searched by their text, `uv run python scripts/fetch_slides.py data` downloads the decks (already committed for GOTO Copenhagen), the first start extracts the text and caches it in git-ignored `slides.json` files. `data/gotocph/README.md`: in the layout block add `<year>/<talk-slug>/slides.json  text cache, git-ignored, rebuilt by the app` and mention `scripts/fetch_slides.py`.

- [ ] **Step 4: Full checks**

Run: `uv run pytest -q && uv run ruff check src tests scripts/fetch_slides.py --output-format concise && uv run ruff format --check && uv run ty check | tail -1 && cd frontend && node --check scripts/record-demo.mjs && npm run check 2>&1 | tail -1 && npm test 2>&1 | rg "Tests" && npm run build 2>&1 | tail -1`
Expected: everything passes.

- [ ] **Step 5: Commit**

```bash
git add frontend/scripts/record-demo.mjs README.md data/gotocph/README.md
git commit -m "Add a zoomed demo tour of the match badges and document slide search"
```

- [ ] **Step 6: Record the zoomed demo**

Start the app on a free port with the placeholder tracker settings and a throwaway database (`ORGESTRA_PORT=8765 ORGESTRA_ISSUES_REPO=demo/demo ORGESTRA_ISSUES_TOKEN=demo ORGESTRA_DB_PATH=$(mktemp -d)/demo.db ORGESTRA_RELOAD=0 uv run orgestra`), run `cd frontend && npm run demo -- --tour slides --base http://127.0.0.1:8765 --out ../demo-slides.mp4` with `CHROMIUM_PATH` set to Chrome, extract two or three frames with ffmpeg and look at them, then stop the server.

- [ ] **Step 7: Final review, push, PR and video**

Run the whole-branch review (fresh reviewer, most capable model) and fix Critical and Important findings test-first. Then load the `git-style` skill, push `claude/slide-search` (no force), open a PR to `main` with a prose body, load `pr-checks`, upload `demo-slides.mp4` as a release asset (`gh release create slide-search-demo ... --prerelease`) and link it from a PR comment (the repo is private).

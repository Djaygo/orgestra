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
    except Exception:  # pypdf raises many error types on damaged files
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

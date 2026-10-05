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

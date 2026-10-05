import re

import pytest
from fastapi.testclient import TestClient

from orgestra.app import REPO_DATA_DIR, Settings, create_app
from orgestra.filters import Filters
from orgestra.highlight import highlight
from tests.conftest import make_talk


def test_highlight_marks_matching_words_and_escapes_the_rest():
    html = highlight("Agents <b>& more</b>", frozenset({"agent"}))

    assert str(html) == "<mark>Agents</mark> &lt;b&gt;&amp; more&lt;/b&gt;"


def test_highlight_matches_inflections_the_way_search_does():
    html = highlight("Testing and tests and tested", frozenset({"test"}))

    assert str(html).count("<mark>") == 3


def test_highlight_never_marks_inside_an_entity_it_made():
    assert str(highlight("AT&T amp", frozenset({"amp"}))) == "AT&amp;T <mark>amp</mark>"


def test_highlight_without_words_only_escapes():
    assert str(highlight("a < b", frozenset())) == "a &lt; b"


def test_filters_ignore_junk_and_keep_real_values():
    assert Filters.parse("abc", "maybe", "") == Filters()
    assert Filters.parse("2025", "1", "1") == Filters(year=2025, slides=True, video=True)
    assert Filters.parse("20255555555555555555555", "", "") == Filters()


def test_filters_keep_only_matching_talks():
    with_both = make_talk("a", year=2025, slides_url="https://x.test/a.pdf", video_url="https://x.test/v")
    plain = make_talk("b", year=2026)

    assert Filters().keeps(with_both) and Filters().keeps(plain)
    assert Filters(year=2025).keeps(with_both) and not Filters(year=2025).keeps(plain)
    assert Filters(slides=True).keeps(with_both) and not Filters(slides=True).keeps(plain)
    assert Filters(video=True).keeps(with_both) and not Filters(video=True).keeps(plain)


def test_filter_urls_keep_the_query_and_the_other_filters():
    filters = Filters(year=2025, slides=True)

    assert filters.url("big data") == "/search?q=big%20data&year=2025&slides=1"
    assert filters.url("big data", year=None) == "/search?q=big%20data&slides=1"
    assert filters.url("x", slides=False, video=True) == "/search?q=x&year=2025&video=1"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "results.db"
    return TestClient(create_app(Settings(data_dir=REPO_DATA_DIR, db_path=db_path)))


def years_of(html: str) -> list[str]:
    return re.findall(r'class="talk-card-title"><a href="/talks/(\d{4})/', html)


def chip_count(html: str, label: str) -> int:
    found = re.search(rf">{label}<span class=\"chip-count\">(\d+)</span>", html)
    assert found, f"no {label} chip with a count"
    return int(found[1])


def test_a_year_filter_narrows_the_cards_but_not_the_counts(client):
    everything = client.get("/search", params={"q": "automation"}).text
    only_2025 = client.get("/search", params={"q": "automation", "year": "2025"}).text

    assert set(years_of(only_2025)) == {"2025"}
    assert len(years_of(only_2025)) == years_of(everything).count("2025")
    assert chip_count(only_2025, "2026") == years_of(everything).count("2026")
    assert chip_count(only_2025, "2025") == years_of(everything).count("2025")


def test_the_slides_filter_keeps_talks_with_a_deck(client):
    everything = client.get("/search", params={"q": "automation"}).text
    with_slides = client.get("/search", params={"q": "automation", "slides": "1"}).text

    assert 0 < len(years_of(with_slides)) < len(years_of(everything))
    assert with_slides.count('title="Slides available"') == len(years_of(with_slides))
    assert chip_count(with_slides, "Slides") == len(years_of(with_slides))
    assert 'href="/search?q=automation" aria-current="true"' in with_slides


def test_junk_parameters_are_ignored(client):
    plain = client.get("/search", params={"q": "automation"}).text
    junk = client.get("/search", params={"q": "automation", "year": "abc", "slides": "maybe"}).text

    assert years_of(junk) == years_of(plain)


def test_a_filter_without_hits_keeps_the_chips_and_offers_to_clear_them(client):
    html = client.get("/search", params={"q": "automation", "year": "1999"}).text

    assert 'class="empty-state"' in html
    assert 'aria-label="Filter results"' in html
    assert "Clear filters" in html


def test_the_summary_counts_the_talks_and_agrees_with_one(client):
    many = client.get("/search", params={"q": "automation"}).text
    one = client.get("/search", params={"q": "openrewrite"}).text

    assert re.search(r"\d+ talks for", many)
    assert "1 talk for" in one


def test_the_live_fragment_carries_the_summary_and_the_filters(client):
    response = client.get("/search", params={"q": "automation"}, headers={"HX-Request": "true"})

    assert response.text.lstrip().startswith('<div id="results"')
    assert "<html" not in response.text
    assert 'class="results-summary"' in response.text
    assert 'aria-label="Filter results"' in response.text


def test_active_filters_ride_along_with_live_searches(client):
    filtered = client.get("/search", params={"q": "automation", "year": "2026", "video": "1"}).text
    plain = client.get("/search", params={"q": "automation"}).text

    assert '<input type="hidden" name="year" value="2026">' in filtered
    assert '<input type="hidden" name="video" value="1">' in filtered
    assert 'type="hidden"' not in plain.split('role="search"')[1].split("</form>")[0]


def test_matched_words_are_highlighted_in_titles_and_snippets(client):
    html = client.get("/search", params={"q": "agents"}).text

    assert "<mark>Agents</mark>" in html or "<mark>agents</mark>" in html


def test_nothing_matched_offers_topics_and_a_way_to_browse(client):
    html = client.get("/search", params={"q": "zzzxqj"}).text

    assert "Nothing matched" in html
    assert 'class="empty-state"' in html
    assert 'href="/search?q=' in html
    assert 'href="/browse"' in html


def test_nothing_matched_hides_the_zero_counts(client):
    html = client.get("/search", params={"q": "zzzxqj"}).text

    assert "0 talks" not in html
    assert 'aria-label="Filter results"' not in html


def test_a_talk_without_details_invents_no_speaker_and_names_its_conference(client):
    html = client.get("/search", params={"q": "agentic automation"}).text

    assert "Speakers not listed yet" in html
    assert "GOTO Copenhagen · 2026" in html

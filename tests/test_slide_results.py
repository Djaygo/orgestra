import pytest

from tests.dirs import client_for, data_dir, write_talk
from tests.pdfs import make_pdf

DECK_URL = "https://slides.example.com/deck.pdf"


@pytest.fixture
def client(tmp_path):
    root = data_dir(tmp_path)
    deck = write_talk(root, "with-deck", slides_url=DECK_URL, slides_file="slides.pdf")
    (deck / "slides.pdf").write_bytes(make_pdf(["Welcome", "Zebra crossing patterns"]))
    write_talk(root, "placeholder-deck", slides_url="__PENDING__", title="Zebra Placeholder Talk")
    return client_for(root, tmp_path)


def test_the_slide_badge_links_to_the_matching_page(client):
    html = client.get("/search", params={"q": "zebra"}).text

    assert f'href="{DECK_URL}#page=2"' in html
    assert ">Slide 2<" in html
    assert 'data-tip="Slides: 0.4"' in html


def test_a_title_match_gets_a_plain_badge_with_its_score(client):
    html = client.get("/search", params={"q": "zebra"}).text

    assert 'class="match" tabindex="0" data-tip="Title: 3.0">Title<' in html


def test_a_talk_with_a_placeholder_has_no_slides_link_anywhere(client):
    results = client.get("/search", params={"q": "zebra"}).text
    talk = client.get("/talks/2025/placeholder-deck").text

    assert "__PENDING__" not in results
    assert "__PENDING__" not in talk
    assert ">Slides<" not in talk


def test_a_talk_with_a_real_deck_links_to_it(client):
    talk = client.get("/talks/2025/with-deck").text

    assert f'href="{DECK_URL}"' in talk

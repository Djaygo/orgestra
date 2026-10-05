import re

import pytest

from tests.dirs import client_for, data_dir, write_talk

YOUTUBE = "https://www.youtube-nocookie.com/embed/ZTfnRXtIFEo"
DECK = "https://slides.example.com/deck.pdf"


@pytest.fixture
def client(tmp_path):
    root = data_dir(tmp_path)
    speakers = [{"slug": "ada", "name": "Ada Lovelace"}]
    write_talk(
        root,
        "full-talk",
        title="A Full Talk",
        section="Keynote",
        day="Thursday",
        start="17:15",
        end="18:15",
        room="Main Stage",
        tags=["ai", "testing"],
        speakers=speakers,
        video_url=YOUTUBE,
        slides_url=DECK,
        abstract="First paragraph.\n\nSecond paragraph.",
    )
    write_talk(root, "sibling", title="A Sibling Talk", tags=["ai"])
    write_talk(root, "evil-video", video_url="https://evil.test/embed/x", slides_url="__PENDING__")
    write_talk(root, "no-details", extracted=False, title=None, abstract=None)
    return client_for(root, tmp_path)


def test_an_embeddable_video_becomes_a_lazy_player(client):
    html = client.get("/talks/2025/full-talk").text

    assert re.search(rf'<iframe class="player-frame"\s+src="{re.escape(YOUTUBE)}"', html)
    assert 'loading="lazy"' in html
    assert 'title="Video: A Full Talk"' in html
    assert "allowfullscreen" in html


def test_an_unknown_video_host_is_a_link_never_a_frame(client):
    html = client.get("/talks/2025/evil-video").text

    assert "<iframe" not in html
    assert 'href="https://evil.test/embed/x"' in html


def test_the_slides_button_needs_a_real_deck(client):
    assert f'href="{DECK}"' in client.get("/talks/2025/full-talk").text
    placeholder = client.get("/talks/2025/evil-video").text
    assert "Open slides" not in placeholder
    assert "__PENDING__" not in placeholder


def test_the_head_has_a_breadcrumb_the_schedule_and_a_way_to_share(client):
    html = client.get("/talks/2025/full-talk").text

    assert 'aria-label="Breadcrumb"' in html
    assert 'href="/browse"' in html
    assert 'href="/browse?tab=2025"' in html
    assert "Keynote" in html
    assert "Thursday 17:15\u201318:15" in html
    assert "Main Stage" in html
    assert "data-copy-link" in html
    assert 'href="https://example.com/full-talk"' in html
    assert 'href="/speakers/ada"' in html


def test_related_talks_are_cards_that_exclude_the_talk_itself(client):
    html = client.get("/talks/2025/full-talk").text
    related = html.split('id="related-heading"')[1].split('id="discussion"')[0]

    assert "A Sibling Talk" in related
    assert "A Full Talk" not in related


def test_a_talk_without_details_says_so_kindly_and_offers_the_schedule(client):
    html = client.get("/talks/2025/no-details").text

    assert "not been extracted yet" in html
    assert 'href="https://example.com/no-details"' in html
    assert 'id="discussion"' in html


def test_the_abstract_keeps_its_paragraphs_and_the_discussion_stays(client):
    html = client.get("/talks/2025/full-talk").text

    assert "<p>First paragraph.</p>" in html
    assert "<p>Second paragraph.</p>" in html
    assert 'class="new-post"' in html

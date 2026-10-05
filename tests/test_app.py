import json

import pytest
from fastapi.testclient import TestClient

from orgestra.app import REPO_DATA_DIR, Settings, create_app, sse_event
from orgestra.events import SPOTLIGHT


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    # The dataset checked in under data/ is the fixture for the routes; the database is a throwaway.
    db_path = tmp_path_factory.mktemp("db") / "orgestra.db"
    return TestClient(create_app(Settings(data_dir=REPO_DATA_DIR, db_path=db_path)))


def test_home_has_search_the_stats_and_stage(client):
    html = client.get("/").text
    assert 'id="q"' in html
    assert "GOTO Copenhagen" in html
    assert 'sse-connect="/conversations/stream"' in html
    cast = html.split('id="cast-data">')[1].split("</script>")[0]
    assert len(json.loads(cast)) > 10


def test_search_fragment_spotlights_the_matching_speakers(client):
    response = client.get("/search", params={"q": "cryptocurrency"}, headers={"HX-Request": "true"})
    assert response.text.lstrip().startswith('<div id="results"')
    assert "<html" not in response.text
    assert "13 years of cryptocurrency" in response.text
    trigger = json.loads(response.headers["HX-Trigger"])
    assert "sarah-meiklejohn" in trigger[SPOTLIGHT]["speakers"]


def test_search_url_renders_the_full_page(client):
    response = client.get("/search", params={"q": "artificial intelligence"})
    assert "<html" in response.text
    assert 'id="results"' in response.text


def test_talk_page(client):
    html = client.get("/talks/2025/13-years-of-cryptocurrency-de-anonymization-and-counting").text
    assert "Sarah Meiklejohn" in html
    assert "Questions this talk answers" in html


def test_speaker_page_shows_links_as_chips_and_hides_what_is_missing(client):
    html = client.get("/speakers/sarah-meiklejohn").text
    assert "Sarah Meiklejohn" in html
    assert "Speaker page" in html
    assert "https://gotocph.com/2025/speakers/" in html
    assert "No public email address" not in html


def test_unknown_pages_are_404(client):
    assert client.get("/talks/2025/nope").status_code == 404
    assert client.get("/speakers/nope").status_code == 404


def test_sse_event_prefixes_every_line():
    assert (
        sse_event("turn", "<li>a</li>\n<li>b</li>") == "event: turn\ndata: <li>a</li>\ndata: <li>b</li>\n\n"
    )


def test_search_page_searches_while_typing(client):
    html = client.get("/search", params={"q": "security"}).text
    assert 'hx-target="#results"' in html
    assert "People also ask" in html


def test_home_is_just_the_search_box(client):
    html = client.get("/").text
    assert 'class="wordmark wordmark-large"' in html
    assert 'hx-target="#results"' not in html


def test_lucky_redirects_to_a_talk_with_details(client):
    response = client.get("/lucky", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/talks/")


def test_results_list_shows_post_counts_and_activity(client):
    ref = "2025/13-years-of-cryptocurrency-de-anonymization-and-counting"
    client.post(f"/talks/{ref}/posts", data={"kind": "comment", "name": "Ada", "body": "Nice talk"})

    html = client.get("/search", params={"q": "cryptocurrency"}).text

    assert 'title="1 post, last activity just now"' in html


def test_home_invites_a_first_search(client):
    html = client.get("/").text
    popular = client.app.state.services.catalog.popular_tags(6)

    assert "I'm feeling curious" in html
    assert "Browse talks" in html
    for tag in popular:
        assert f'href="/search?q={tag.replace(" ", "%20")}"' in html or f">{tag}<" in html
    assert len(popular) == 6
    assert "135 talks" in html
    assert "65 speakers" in html
    assert "<kbd>/</kbd>" in html
    assert 'role="combobox"' in html
    assert 'id="suggestions"' in html

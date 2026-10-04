import json

import pytest
from fastapi.testclient import TestClient

from orgestra.app import REPO_DATA_DIR, Settings, create_app, sse_event
from orgestra.events import SPOTLIGHT


@pytest.fixture(scope="module")
def client():
    # The dataset checked in under data/ is the fixture for the routes.
    return TestClient(create_app(Settings(data_dir=REPO_DATA_DIR)))


def test_home_has_search_sidebar_and_stage(client):
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


def test_speaker_page_shows_contact_info(client):
    html = client.get("/speakers/sarah-meiklejohn").text
    assert "Contact" in html
    assert "No public email address" in html
    assert "https://gotocph.com/2025/speakers/" in html


def test_unknown_pages_are_404(client):
    assert client.get("/talks/2025/nope").status_code == 404
    assert client.get("/speakers/nope").status_code == 404


def test_sse_event_prefixes_every_line():
    assert (
        sse_event("turn", "<li>a</li>\n<li>b</li>") == "event: turn\ndata: <li>a</li>\ndata: <li>b</li>\n\n"
    )

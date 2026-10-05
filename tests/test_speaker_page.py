import pytest

from tests.dirs import client_for, data_dir, write_speaker, write_talk


@pytest.fixture
def client(tmp_path):
    root = data_dir(tmp_path)
    ada = [{"slug": "ada", "name": "Ada Lovelace"}]
    write_talk(root, "first", year=2025, title="First Talk", speakers=ada)
    write_talk(root, "second", year=2026, title="Second Talk", speakers=ada)
    write_speaker(
        root,
        "ada",
        name="Ada Lovelace",
        role_company="Mathematician, Analytical Engines",
        bio="Wrote the first program.",
        email="ada@example.com",
        links={"Website": "https://ada.example.com"},
        profiles={"2025": "https://conf.example.com/2025/speakers/1/ada"},
        talks=["2025/first", "2026/second"],
    )
    write_speaker(root, "quiet", name="Quiet Person")
    return client_for(root, tmp_path)


def test_the_header_shows_who_they_are(client):
    html = client.get("/speakers/ada").text

    assert "<h1>Ada Lovelace</h1>" in html
    assert "Mathematician, Analytical Engines" in html
    assert "Wrote the first program." in html
    assert ">AL<" in html


def test_links_become_chips_and_the_email_is_a_mailto(client):
    html = client.get("/speakers/ada").text

    assert 'href="mailto:ada@example.com"' in html
    assert 'href="https://ada.example.com"' in html
    assert "Speaker page 2025" in html
    assert 'href="https://conf.example.com/2025/speakers/1/ada"' in html


def test_their_talks_are_cards_newest_year_first(client):
    html = client.get("/speakers/ada").text

    assert html.index("Second Talk") < html.index("First Talk")
    assert 'class="talk-card' in html


def test_nothing_is_said_about_a_missing_email_or_missing_talks(client):
    html = client.get("/speakers/quiet").text

    assert "mailto:" not in html
    assert "No public email" not in html
    assert 'class="talk-card' not in html
    assert "<h2>Talks</h2>" not in html

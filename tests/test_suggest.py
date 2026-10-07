import pytest
from fastapi.testclient import TestClient

from orgestra.app import REPO_DATA_DIR, Settings, create_app
from orgestra.dataset import Catalog, Speaker
from orgestra.suggest import Suggestion, suggest
from tests.conftest import make_talk


def catalog_of(*talks, speakers=()):
    return Catalog(
        organizations=[],
        talks={talk.ref: talk for talk in talks},
        speakers={speaker.slug: speaker for speaker in speakers},
    )


@pytest.mark.parametrize("query", ["", "  ", "k", " a "])
def test_blank_and_one_letter_queries_suggest_nothing(catalog, query):
    assert suggest(catalog, query) == []


def test_a_title_prefix_finds_the_talk_and_skips_talks_without_a_title(catalog):
    found = suggest(catalog, "kub")

    assert [(s.kind, s.label, s.href) for s in found] == [
        ("talk", "Kubernetes at Scale", "/talks/2025/kubernetes-at-scale")
    ]


def test_matching_ignores_case(catalog):
    assert [s.label for s in suggest(catalog, "KUBER")] == ["Kubernetes at Scale"]


def test_speakers_and_topics_have_their_own_links(catalog):
    [speaker] = suggest(catalog, "ada")
    [topic, *_] = suggest(catalog, "plat")

    assert (speaker.kind, speaker.label, speaker.href) == ("speaker", "Ada Lovelace", "/speakers/ada")
    assert (topic.kind, topic.label, topic.href) == ("topic", "platforms", "/search?q=platforms")


def test_a_prefix_beats_a_word_prefix_beats_a_substring_and_topics_lead_ties():
    catalog = catalog_of(
        make_talk("explanation", title="Explanation of things", tags=["platforms"]),
        make_talk("planet", title="Planet Scale"),
        make_talk("grand", title="The grand plan"),
    )

    labels = [s.label for s in suggest(catalog, "pla")]

    assert labels == ["platforms", "Planet Scale", "The grand plan", "Explanation of things"]


def test_a_topic_spelled_in_several_cases_is_suggested_once():
    catalog = catalog_of(
        make_talk("a", tags=["AI agents"]),
        make_talk("d", tags=["AI agents"]),
        make_talk("b", tags=["AI Agents"]),
        make_talk("c", tags=["ai agents"]),
    )

    assert [s.label for s in suggest(catalog, "agents")] == ["AI agents"]


def test_at_most_limit_suggestions():
    catalog = catalog_of(*(make_talk(f"talk-{n}", title=f"Testing part {n}") for n in range(10)))

    assert len(suggest(catalog, "testing", limit=4)) == 4
    assert len(suggest(catalog, "testing")) == 6


def test_a_speaker_shows_their_role_and_a_talk_its_year_and_speakers():
    catalog = catalog_of(
        make_talk("t", title="Zebra talk", speakers=[{"slug": "zed", "name": "Zed Zebra"}]),
        speakers=[Speaker(slug="zed", name="Zed Zebra", role_company="Herder, Zoo")],
    )

    talk, speaker = sorted(suggest(catalog, "zeb"), key=lambda s: s.kind, reverse=True)

    assert talk.detail == "2025 · Zed Zebra"
    assert speaker.detail == "Herder, Zoo"


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(Settings(data_dir=REPO_DATA_DIR, db_path=tmp_path / "test.db")))


def test_the_route_returns_options_that_are_never_cached(client):
    response = client.get("/suggest", params={"q": "agents"})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert 'role="option"' in response.text
    assert 'href="/talks/' in response.text


def test_the_route_is_empty_for_a_blank_query(client):
    assert client.get("/suggest", params={"q": ""}).text.strip() == ""


def test_labels_are_escaped_in_the_fragment(client):
    templates = client.app.state.services.templates
    hostile = Suggestion(kind="talk", label="<b>x</b> & y", href="/talks/2025/x", detail='"quoted"')

    html = templates.get_template("partials/suggest.html").render(suggestions=[hostile])

    assert "<b>x</b>" not in html
    assert "&lt;b&gt;x&lt;/b&gt; &amp; y" in html

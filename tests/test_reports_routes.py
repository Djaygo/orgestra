import attrs
import pytest
from fastapi.testclient import TestClient

from orgestra.app import REPO_DATA_DIR, Settings, create_app
from orgestra.reports.tracker import Issue, TrackerError

TALK = "/talks/2025/13-years-of-cryptocurrency-de-anonymization-and-counting"
VALID = {"title": "Search is broken", "description": "Typing does nothing", "page": TALK}


class FakeTracker:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def create_issue(self, title: str, body: str) -> Issue:
        self.calls.append((title, body))
        if self.error:
            raise self.error
        return Issue(number=7)


def make_client(tmp_path, tracker) -> TestClient:
    app = create_app(Settings(data_dir=REPO_DATA_DIR, db_path=tmp_path / "test.db"))
    app.state.services = attrs.evolve(app.state.services, tracker=tracker)
    return TestClient(app)


@pytest.fixture
def tracker():
    return FakeTracker()


@pytest.fixture
def client(tmp_path, tracker):
    return make_client(tmp_path, tracker)


def test_the_form_keeps_the_page_it_came_from(client):
    html = client.get("/report", params={"from": TALK}).text

    assert f'name="page" value="{TALK}"' in html
    assert 'maxlength="120"' in html
    assert 'maxlength="5000"' in html


@pytest.mark.parametrize("origin", ["//evil.com", "/\\evil.com", "https://evil.com", "javascript:alert(1)"])
def test_an_external_origin_is_dropped(client, origin):
    html = client.get("/report", params={"from": origin}).text

    assert 'name="page" value=""' in html
    assert "evil.com" not in html


def test_filing_a_report_shows_the_issue_number_and_sends_the_context(client, tracker):
    response = client.post("/report", data=VALID, headers={"user-agent": "TestBrowser/1.0"})

    assert response.status_code == 200
    assert "#7" in response.text
    assert f'href="{TALK}"' in response.text
    ((title, body),) = tracker.calls
    assert title == "[site] Search is broken"
    assert "Typing does nothing" in body
    assert f"Page: {TALK}" in body
    assert "Browser: TestBrowser/1.0" in body


def test_an_external_page_in_the_post_is_dropped_from_the_issue(client, tracker):
    client.post("/report", data=VALID | {"page": "//evil.com"})

    assert "evil.com" not in tracker.calls[0][1]


def test_a_forge_failure_shows_a_plain_page_and_nothing_secret(tmp_path, caplog):
    failing = FakeTracker(TrackerError("GitHub answered 500: boom-body"))
    client = make_client(tmp_path, failing)

    response = client.post("/report", data=VALID)

    assert response.status_code == 502
    assert "try again later" in response.text
    assert "boom-body" not in response.text
    assert "GitHub answered" not in response.text
    assert "boom-body" in caplog.text


@pytest.mark.parametrize(
    "fields",
    [
        {"title": "   "},
        {"description": "   "},
        {"title": "x" * 121},
        {"description": "x" * 5001},
    ],
)
def test_blank_and_over_long_fields_are_rejected_and_nothing_is_filed(client, tracker, fields):
    response = client.post("/report", data=VALID | fields)

    assert response.status_code == 422
    assert tracker.calls == []


def test_the_button_links_to_the_current_page(client):
    assert 'class="report-button" href="/report?from=/"' in client.get("/").text
    assert f'href="/report?from={TALK}"' in client.get(TALK).text
    assert 'href="/report?from=/search%3Fq%3Dagents"' in client.get("/search", params={"q": "agents"}).text
    assert 'class="report-button"' not in client.get("/report").text


def test_without_a_tracker_the_feature_is_off(tmp_path):
    client = make_client(tmp_path, None)

    assert "Report a bug" not in client.get("/").text
    assert client.get("/report").status_code == 404
    assert client.post("/report", data=VALID).status_code == 404
    assert client.post("/report", data={"title": ""}).status_code == 404


def test_the_token_is_never_rendered_or_shown_in_the_settings_repr(tmp_path):
    settings = Settings(
        data_dir=REPO_DATA_DIR,
        db_path=tmp_path / "test.db",
        issues_repo="owner/name",
        issues_token="tok-secret-xyz",  # noqa: S106 - a fake token the test looks for in pages
    )
    client = TestClient(create_app(settings))

    assert "tok-secret-xyz" not in repr(settings)
    for path in ("/", "/report", TALK):
        assert "tok-secret-xyz" not in client.get(path).text
    assert 'class="report-button"' in client.get("/").text


def test_an_unknown_provider_fails_at_startup(tmp_path):
    with pytest.raises(ValueError, match="gitlab"):
        create_app(Settings(data_dir=REPO_DATA_DIR, db_path=tmp_path / "test.db", issues_provider="gitlab"))

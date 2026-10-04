# Bug Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A "Report a bug" button on every page lets a visitor file an issue on the project's forge (GitHub now, GitLab later) without seeing or needing a forge account.

**Architecture:** A `reports` package holds an `IssueTracker` protocol, a `GitHubIssues` adapter over the REST API, and a pure body builder. `Settings` carries the provider, repository and token; `build_tracker` returns a tracker or `None`, stored on `Services`. `/report` routes render the form and the result pages, and answer 404 when no tracker is configured. GitLab later is one more adapter and one more branch in `build_tracker`.

**Tech Stack:** FastAPI, Jinja2, pydantic form models, `httpx2` (the HTTP client Starlette 1.7 already requires; same `Client`/`MockTransport` API as `httpx`), pytest, ruff, ty.

**Spec:** `docs/superpowers/specs/2026-10-04-bug-reports-design.md`

## Global Constraints

- Dependencies only through `uv add` / `uv remove` (never edit `pyproject.toml` by hand). The HTTP client is `httpx2`: plain `httpx` is not installed, and the spec's "httpx" means this client. It moves from the dev group to the runtime dependencies.
- The token never reaches the browser, a log line or a page; `Settings` keeps it out of its `repr`.
- No rate limit, honeypot or captcha, no labels, no assignees, no link to the issue on the thank-you page, no use of the SQLite database.
- `ORGESTRA_ISSUES_PROVIDER` defaults to `github`; any other value fails at startup. The feature is enabled only when both `ORGESTRA_ISSUES_REPO` and `ORGESTRA_ISSUES_TOKEN` are set; otherwise the button is hidden and `/report` answers 404 for both methods.
- Title 1 to 120 characters, description 1 to 5000 characters, after trimming; violations answer 422 and file nothing.
- Forge timeout 10 s; any failure shows a plain 502 page and the real error goes only to the server log.
- Line length 110; `uv run ruff check src tests`, `uv run ruff format --check` and `uv run ty check` must pass (4 older `ruff check` errors in `scripts/build_gotocph_dataset.py` are out of scope).
- Comments describe the current state only; never remove existing comments or docstrings.
- Commits end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; plain imperative style, no amending, no force-push, and never `git add` a `.envrc` or any file holding a token.

## Review Focus

- A `page`/`from` value that is external or protocol-relative (`//evil.com`, `/\evil.com`, `https://evil.com`, `javascript:alert(1)`) must be dropped, never rendered as a link target (Task 3).
- A description, page or user agent containing backtick runs or `@mentions` must stay inside its fence and never become markup in the issue (Task 1).
- A forge failure must show the visitor no status, body or token, and the adapter's error text must never contain the token (Tasks 2 and 3).
- With no tracker configured, both `GET` and `POST /report` must answer 404 even for an invalid form, and the button must be absent (Task 3).
- An unknown `ORGESTRA_ISSUES_PROVIDER` must fail at startup with a message naming it (Tasks 2 and 3).

## File Structure

| File | Responsibility |
|---|---|
| `src/orgestra/reports/__init__.py` | package marker |
| `src/orgestra/reports/tracker.py` | `Issue`, `TrackerError`, `IssueTracker` protocol |
| `src/orgestra/reports/body.py` | `issue_title`, `issue_body` (fenced description and context) |
| `src/orgestra/reports/github.py` | `GitHubIssues` adapter |
| `src/orgestra/reports/build.py` | `build_tracker(provider, repo, token)` |
| `src/orgestra/reports/routes.py` | `/report` routes, form model, `safe_page` |
| `src/orgestra/templates/report.html`, `report_sent.html`, `report_failed.html` | form and result pages |
| `src/orgestra/templates/base.html`, `static/css/app.css` | top-bar button and form styles |
| `src/orgestra/app.py` | settings, services, layout context, router |
| `tests/test_reports_*.py` | body, adapter and builder, routes |
| `frontend/scripts/record-demo.mjs`, `README.md`, `CLAUDE.md`, the spec | demo step and docs |

---

### Task 1: HTTP client dependency, tracker protocol and issue body

**Files:**
- Modify: `pyproject.toml`, `uv.lock` (through `uv`)
- Create: `src/orgestra/reports/__init__.py`, `src/orgestra/reports/tracker.py`, `src/orgestra/reports/body.py`
- Test: `tests/test_reports_body.py`

**Interfaces:**
- Produces: `Issue(number: int)` (frozen attrs), `TrackerError(Exception)`, `IssueTracker` (`typing.Protocol` with `create_issue(self, title: str, body: str) -> Issue`), `issue_title(title: str) -> str`, `issue_body(description: str, page: str, user_agent: str, now: datetime) -> str`.

- [ ] **Step 1: Make `httpx2` a runtime dependency**

Run: `uv add httpx2 && uv remove --dev httpx2 && uv run python -c "import httpx2; print(httpx2.Client)"`
Expected: `httpx2` listed under `dependencies`, no longer under the dev group, and the import prints the class.

- [ ] **Step 2: Write the failing tests**

`tests/test_reports_body.py`:

```python
from datetime import datetime

from orgestra.reports.body import issue_body, issue_title

NOW = datetime(2026, 10, 4, 12, 30)


def test_title_is_prefixed_with_the_site():
    assert issue_title("Broken search") == "[site] Broken search"


def test_body_fences_the_description_and_the_context():
    body = issue_body("it fails\non click", "/talks/2025/x", "Mozilla/5.0", NOW)

    assert body == (
        "## Description\n\n```\nit fails\non click\n```\n\n"
        "## Context\n\n```\nPage: /talks/2025/x\nBrowser: Mozilla/5.0\nReported: 2026-10-04 12:30 UTC\n```\n"
    )


def test_a_longer_fence_wraps_text_containing_backticks_and_mentions():
    body = issue_body("a ```code``` b @octocat", "/", "UA", NOW)

    assert "````\na ```code``` b @octocat\n````" in body


def test_the_context_cannot_break_out_of_its_fence_either():
    body = issue_body("ok", "/p", "UA ```` @mention", NOW)

    assert "`````\nPage: /p\nBrowser: UA ```` @mention" in body
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_reports_body.py -q`
Expected: FAIL with `ModuleNotFoundError: orgestra.reports`.

- [ ] **Step 4: Implement**

Create empty `src/orgestra/reports/__init__.py`.

`src/orgestra/reports/tracker.py`:

```python
"""The seam between the bug report form and a forge (GitHub today, GitLab later)."""

from __future__ import annotations

from typing import Protocol

import attrs


@attrs.frozen
class Issue:
    number: int


class TrackerError(Exception):
    """The forge did not create the issue. The message is for the server log, never for a visitor."""


class IssueTracker(Protocol):
    def create_issue(self, title: str, body: str) -> Issue: ...
```

`src/orgestra/reports/body.py`:

```python
"""The text of the issue filed for a bug report. Everything visitors control sits inside a fence."""

from __future__ import annotations

import re
from datetime import datetime

MIN_FENCE = 3


def fenced(text: str) -> str:
    """The text in a code fence longer than any backtick run inside it, so it cannot break out."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(MIN_FENCE, longest + 1)
    return f"{fence}\n{text}\n{fence}"


def issue_title(title: str) -> str:
    return f"[site] {title}"


def issue_body(description: str, page: str, user_agent: str, now: datetime) -> str:
    context = f"Page: {page}\nBrowser: {user_agent}\nReported: {now:%Y-%m-%d %H:%M} UTC"
    return f"## Description\n\n{fenced(description)}\n\n## Context\n\n{fenced(context)}\n"
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_reports_body.py -q && uv run ruff check src tests --output-format concise && uv run ruff format --check && uv run ty check | tail -1`
Expected: 4 passed, all clean.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/orgestra/reports tests/test_reports_body.py
git commit -m "Add the issue tracker protocol and the bug report issue body"
```

---

### Task 2: GitHub adapter and tracker builder

**Files:**
- Create: `src/orgestra/reports/github.py`, `src/orgestra/reports/build.py`
- Test: `tests/test_reports_github.py`

**Interfaces:**
- Consumes: `Issue`, `TrackerError`, `IssueTracker` (Task 1).
- Produces: `GitHubIssues(repo: str, token: str, client: httpx2.Client)` with `create_issue(title, body) -> Issue`; `build_tracker(provider: str, repo: str, token: str) -> IssueTracker | None` (raises `ValueError` for an unknown provider; `None` when the repo or token is empty).

- [ ] **Step 1: Write the failing tests**

`tests/test_reports_github.py`:

```python
import json

import httpx2
import pytest

from orgestra.reports.build import build_tracker
from orgestra.reports.github import GitHubIssues
from orgestra.reports.tracker import Issue, TrackerError

TOKEN = "secret-token-123"


def tracker_with(handler) -> GitHubIssues:
    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    return GitHubIssues("owner/name", TOKEN, client)


def test_creates_an_issue_with_the_documented_request():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["headers"] = {
            name: request.headers[name] for name in ("authorization", "accept", "x-github-api-version")
        }
        seen["json"] = json.loads(request.content)
        return httpx2.Response(201, json={"number": 42})

    issue = tracker_with(handler).create_issue("A title", "A body")

    assert issue == Issue(number=42)
    assert seen == {
        "url": "https://api.github.com/repos/owner/name/issues",
        "headers": {
            "authorization": f"Bearer {TOKEN}",
            "accept": "application/vnd.github+json",
            "x-github-api-version": "2022-11-28",
        },
        "json": {"title": "A title", "body": "A body"},
    }


@pytest.mark.parametrize("status", [401, 403, 404, 422, 500])
def test_any_other_status_is_an_error_that_names_it(status):
    tracker = tracker_with(lambda request: httpx2.Response(status, json={"message": "nope"}))

    with pytest.raises(TrackerError, match=str(status)):
        tracker.create_issue("t", "b")


def test_a_network_error_is_a_tracker_error():
    def handler(request):
        raise httpx2.ConnectTimeout("too slow")

    with pytest.raises(TrackerError, match="ConnectTimeout"):
        tracker_with(handler).create_issue("t", "b")


@pytest.mark.parametrize(
    "response",
    [
        httpx2.Response(201, text="not json"),
        httpx2.Response(201, json={}),
        httpx2.Response(201, json={"number": "7"}),
        httpx2.Response(201, json=[1, 2]),
    ],
)
def test_a_success_without_an_issue_number_is_an_error(response):
    with pytest.raises(TrackerError, match="issue number"):
        tracker_with(lambda request: response).create_issue("t", "b")


def test_errors_and_repr_never_contain_the_token():
    tracker = tracker_with(lambda request: httpx2.Response(401, json={"message": "Bad credentials"}))

    with pytest.raises(TrackerError) as raised:
        tracker.create_issue("t", "b")

    assert TOKEN not in str(raised.value)
    assert TOKEN not in repr(tracker)


def test_build_tracker_builds_github_only_when_repo_and_token_are_set():
    assert build_tracker("github", "", "") is None
    assert build_tracker("github", "owner/name", "") is None
    assert build_tracker("github", "", TOKEN) is None
    assert isinstance(build_tracker("github", "owner/name", TOKEN), GitHubIssues)


def test_an_unknown_provider_is_an_error_even_when_disabled():
    with pytest.raises(ValueError, match="gitlab"):
        build_tracker("gitlab", "", "")
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_reports_github.py -q`
Expected: FAIL with `ModuleNotFoundError: orgestra.reports.github`.

- [ ] **Step 3: Implement the adapter**

`src/orgestra/reports/github.py`:

```python
"""Files issues on GitHub through the REST API."""

from __future__ import annotations

import httpx2

from orgestra.reports.tracker import Issue, TrackerError

API = "https://api.github.com"
CREATED = 201
ERROR_BODY_CHARS = 300


class GitHubIssues:
    def __init__(self, repo: str, token: str, client: httpx2.Client) -> None:
        self._repo = repo
        self._token = token
        self._client = client

    def create_issue(self, title: str, body: str) -> Issue:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        try:
            response = self._client.post(
                f"{API}/repos/{self._repo}/issues", headers=headers, json={"title": title, "body": body}
            )
        except httpx2.HTTPError as error:
            raise TrackerError(f"GitHub request failed: {type(error).__name__}") from error
        if response.status_code != CREATED:
            raise TrackerError(f"GitHub answered {response.status_code}: {response.text[:ERROR_BODY_CHARS]}")
        return Issue(number=self._issue_number(response))

    @staticmethod
    def _issue_number(response: httpx2.Response) -> int:
        try:
            number = response.json()["number"]
        except (ValueError, KeyError, TypeError) as error:
            raise TrackerError("GitHub answered 201 without an issue number") from error
        if not isinstance(number, int):
            raise TrackerError("GitHub answered 201 without an issue number")
        return number
```

`src/orgestra/reports/build.py`:

```python
"""Picks the forge adapter from configuration."""

from __future__ import annotations

import httpx2

from orgestra.reports.github import GitHubIssues
from orgestra.reports.tracker import IssueTracker

TIMEOUT_S = 10


def build_tracker(provider: str, repo: str, token: str) -> IssueTracker | None:
    """The tracker, or None when reporting is not configured (no repository or no token)."""
    if provider != "github":
        raise ValueError(f"unknown issue provider {provider!r}; supported: github")
    if not (repo and token):
        return None
    return GitHubIssues(repo, token, httpx2.Client(timeout=TIMEOUT_S))
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_reports_github.py -q && uv run ruff check src tests --output-format concise && uv run ruff format --check && uv run ty check | tail -1`
Expected: 14 passed (1 + 5 + 1 + 4 + 1 + 1 + 1), clean. If ty rejects `_issue_number` being a staticmethod called on `self`, call it as `GitHubIssues._issue_number(response)` is not needed: fix the call, not the design.

- [ ] **Step 5: Commit**

```bash
git add src/orgestra/reports tests/test_reports_github.py
git commit -m "Add the GitHub issue adapter and the tracker builder"
```

---

### Task 3: Settings, routes, templates and the top-bar button

**Files:**
- Modify: `src/orgestra/app.py`, `src/orgestra/templates/base.html`, `src/orgestra/static/css/app.css`
- Create: `src/orgestra/reports/routes.py`, `src/orgestra/templates/report.html`, `src/orgestra/templates/report_sent.html`, `src/orgestra/templates/report_failed.html`
- Test: `tests/test_reports_routes.py`

**Interfaces:**
- Consumes: `build_tracker`, `IssueTracker`, `Issue`, `TrackerError`, `issue_title`, `issue_body` (Tasks 1 and 2); `utc_now` from `orgestra.discussion.models`.
- Produces: `Settings.issues_provider: str = "github"`, `Settings.issues_repo: str = ""`, `Settings.issues_token: str = ""` (not in `repr`); `Services.tracker: IssueTracker | None`; template globals `reports_enabled: bool` and `report_from: str` (path plus query of the current request); `reports.routes.router`; `safe_page(value: str) -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_reports_routes.py`:

```python
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
    (title, body), = tracker.calls
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
        issues_token="tok-secret-xyz",
    )
    client = TestClient(create_app(settings))

    assert "tok-secret-xyz" not in repr(settings)
    for path in ("/", "/report", TALK):
        assert "tok-secret-xyz" not in client.get(path).text
    assert 'class="report-button"' in client.get("/").text


def test_an_unknown_provider_fails_at_startup(tmp_path):
    with pytest.raises(ValueError, match="gitlab"):
        create_app(Settings(data_dir=REPO_DATA_DIR, db_path=tmp_path / "test.db", issues_provider="gitlab"))
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_reports_routes.py -q 2>&1 | tail -6`
Expected: FAIL (errors on `evolve(... tracker=...)` and missing `issues_*` settings).

- [ ] **Step 3: Settings, services and layout context in `src/orgestra/app.py`**

Add imports: `from orgestra.reports import routes as reports_routes`, `from orgestra.reports.build import build_tracker`, `from orgestra.reports.tracker import IssueTracker`.

Extend `Settings` (keep the existing fields):

```python
    issues_provider: str = "github"
    issues_repo: str = ""
    issues_token: str = attrs.field(default="", repr=False)
```

and in `from_env` add:

```python
            issues_provider=os.environ.get("ORGESTRA_ISSUES_PROVIDER", "github"),
            issues_repo=os.environ.get("ORGESTRA_ISSUES_REPO", ""),
            issues_token=os.environ.get("ORGESTRA_ISSUES_TOKEN", ""),
```

Add `tracker: IssueTracker | None` as the last field of `Services`, and in `build_services` add `tracker=build_tracker(settings.issues_provider, settings.issues_repo, settings.issues_token),`.

Replace the context processor in `build_templates` (the `lambda _request: layout`) with a function defined just above `templates = Jinja2Templates(`:

```python
    def layout_context(request: Request) -> dict[str, object]:
        query = f"?{request.url.query}" if request.url.query else ""
        return layout | {
            "reports_enabled": request.app.state.services.tracker is not None,
            "report_from": request.url.path + query,
        }
```

and pass `context_processors=[layout_context]`. In `create_app` add `app.include_router(reports_routes.router)` after the discussion router.

- [ ] **Step 4: Routes**

`src/orgestra/reports/routes.py`:

```python
"""The bug report form: filed as an issue on the forge, or a plain error page when that fails."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, StringConstraints

from orgestra.discussion.models import utc_now
from orgestra.reports.body import issue_body, issue_title
from orgestra.reports.tracker import IssueTracker, TrackerError

logger = logging.getLogger(__name__)
MAX_PAGE_CHARS = 500

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class Report(BaseModel):
    title: Title
    description: Description
    page: str = ""


router = APIRouter()


def safe_page(value: str) -> str:
    """A path on this site, or empty: external, protocol-relative and backslash forms are dropped."""
    local = value.startswith("/") and value[1:2] not in ("/", "\\")
    return value if local and len(value) <= MAX_PAGE_CHARS else ""


def require_tracker(request: Request) -> IssueTracker:
    tracker = request.app.state.services.tracker
    if tracker is None:
        raise HTTPException(status_code=404, detail="Not found")
    return tracker


Tracker = Annotated[IssueTracker, Depends(require_tracker)]


def render(request: Request, name: str, context: dict[str, Any], status_code: int = 200) -> HTMLResponse:
    templates = request.app.state.services.templates
    return templates.TemplateResponse(request, name, context, status_code=status_code)


@router.get("/report", response_class=HTMLResponse)
def report_form(
    request: Request, _: Tracker, origin: Annotated[str, Query(alias="from", max_length=2000)] = ""
) -> HTMLResponse:
    return render(request, "report.html", {"page": safe_page(origin)})


@router.post("/report", response_class=HTMLResponse)
def send_report(request: Request, tracker: Tracker, form: Annotated[Report, Form()]) -> HTMLResponse:
    page = safe_page(form.page)
    body = issue_body(form.description, page, request.headers.get("user-agent", ""), utc_now())
    try:
        issue = tracker.create_issue(issue_title(form.title), body)
    except TrackerError as error:
        logger.error("could not file a bug report: %s", error)
        return render(request, "report_failed.html", {"page": page}, status_code=502)
    return render(request, "report_sent.html", {"number": issue.number, "page": page})
```

- [ ] **Step 5: Templates, button and styles**

`templates/report.html`:

```jinja
{% extends "base.html" %}
{% block title %}Report a bug · Orgestra{% endblock %}
{% block content %}
  <article class="report">
    <h1>Report a bug</h1>
    <p class="muted">Tell us what went wrong. Your report goes straight to the people who build this site.</p>
    <form class="report-form" method="post" action="/report" hx-boost="false">
      <input type="hidden" name="page" value="{{ page }}">
      <label>Title
        <input name="title" maxlength="120" required>
      </label>
      <label>What happened?
        <textarea name="description" rows="6" maxlength="5000" required></textarea>
      </label>
      <p>
        <button class="button" type="submit">Send report</button>
        <a href="{{ page or '/' }}">Cancel</a>
      </p>
    </form>
  </article>
{% endblock %}
```

`templates/report_sent.html`:

```jinja
{% extends "base.html" %}
{% block title %}Report sent · Orgestra{% endblock %}
{% block content %}
  <article class="report">
    <h1>Thanks, your report was filed as #{{ number }}</h1>
    <p>
      <a href="{{ page or '/' }}">Back to where you were</a>
    </p>
  </article>
{% endblock %}
```

`templates/report_failed.html`:

```jinja
{% extends "base.html" %}
{% block title %}Report not sent · Orgestra{% endblock %}
{% block content %}
  <article class="report">
    <h1>We could not send your report</h1>
    <p>Please try again later.</p>
    <p>
      <a href="{{ page or '/' }}">Back to where you were</a>
    </p>
  </article>
{% endblock %}
```

In `base.html`, replace `<label for="sources-toggle" class="sources-button">Sources</label>` with:

```jinja
            {% if reports_enabled %}
              <a class="report-button" href="/report?from={{ report_from|urlencode }}">Report a bug</a>
            {% endif %}
            <label for="sources-toggle" class="sources-button">Sources</label>
```

Append to `app.css` just before the first `@media` block:

```css
/* Bug report */
.report-button { margin-left: auto; color: var(--muted); padding: 0.5rem; border-radius: 4px; }
.report-button:hover { background: var(--hover); text-decoration: none; }
.report-button + .sources-button { margin-left: 0; }
.home .report-button { position: absolute; top: 1rem; right: 6.5rem; }
.report { max-width: 720px; }
.report h1 { font-weight: 400; font-size: 28px; margin: 0.25rem 0 0.75rem; }
.report-form { display: grid; gap: 1rem; }
.report-form label { display: grid; gap: 0.35rem; color: var(--muted); }
.report-form input, .report-form textarea {
  font: inherit;
  color: var(--text);
  background: var(--box);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.5rem 0.7rem;
}
.report-form .button { margin: 0 0.75rem 0 0; }
```

- [ ] **Step 6: Run to verify it passes**

Run: `uv run pytest -q && uv run ruff check src tests --output-format concise && uv run ruff format --check && uv run ty check | tail -1`
Expected: all tests pass (the new file's 16 plus the existing suite), clean. If ruff format reflows the test file, run `uv run ruff format tests` and re-run.

- [ ] **Step 7: Commit**

```bash
git add src tests
git commit -m "Add the bug report form and button, filed through the issue tracker"
```

---

### Task 4: Demo step, docs and delivery

**Files:**
- Modify: `frontend/scripts/record-demo.mjs`, `README.md`, `CLAUDE.md`, `docs/superpowers/specs/2026-10-04-bug-reports-design.md`

**Interfaces:**
- Consumes: markup from Task 3 (`.report-button`, `form.report-form` with `input[name=title]` and `textarea[name=description]`).

- [ ] **Step 1: Add the demo step**

In `record-demo.mjs`, add above `tour`:

```js
/** Report a bug: open the form from the top bar and fill it in, without sending anything. */
async function reportBug(page) {
  const button = page.locator(".report-button");
  if (!(await button.count())) {
    return;
  }
  await button.click();
  await page.waitForSelector("form.report-form");
  const form = page.locator("form.report-form");
  await form.locator("input[name=title]").pressSequentially("The search box loses my query", { delay: 50 });
  await form.locator("textarea[name=description]").pressSequentially("I typed a long query, switched tabs and it was gone.", { delay: 40 });
  log("report form filled in");
  await pause(page, 2500);
  await page.goBack();
}
```

and in `tour`, right after `log("back"); await pause(page, 2000);` add `await reportBug(page);`.

- [ ] **Step 2: Document the settings and the demo setup**

In `README.md`, add to the settings paragraph: `ORGESTRA_ISSUES_PROVIDER` (`github`), `ORGESTRA_ISSUES_REPO` (`owner/name`) and `ORGESTRA_ISSUES_TOKEN` (a fine-grained token with Issues read and write on that repository; the "Report a bug" button is hidden unless both repo and token are set). In `CLAUDE.md` step 2 of the demo list, extend the command to `ORGESTRA_ISSUES_REPO=demo/demo ORGESTRA_ISSUES_TOKEN=demo ORGESTRA_DB_PATH=$(mktemp -d)/demo.db uv run orgestra`, with the sentence "the placeholder repo and token show the Report a bug button without ever filing a real issue (the demo does not submit it)".

- [ ] **Step 3: Align the spec with what was built**

In the spec, change "`httpx`" to "`httpx2`" in the Components table and the GitHub adapter paragraph (with the note "the client Starlette 1.7 already requires; `httpx` is not installed"), and change the issue-body bullet to "a "Context" heading and a second fenced block with the page path, the browser's `User-Agent` header and the UTC time (fenced because the visitor controls the page and header values)".

- [ ] **Step 4: Run every check**

Run: `uv run pytest -q && uv run ruff check src tests --output-format concise && uv run ruff format --check && uv run ty check | tail -1 && cd frontend && node --check scripts/record-demo.mjs && npm run check 2>&1 | tail -1 && npm test 2>&1 | rg "Tests" && npm run build 2>&1 | tail -1`
Expected: everything passes.

- [ ] **Step 5: Commit**

```bash
git add frontend/scripts/record-demo.mjs README.md CLAUDE.md docs
git commit -m "Show the bug report form in the demo tour and document the settings"
```

- [ ] **Step 6: Record the demo and check the real flow without filing anything**

Start the app on a free port with the placeholder repo and token and a throwaway database (`ORGESTRA_PORT=8765 ORGESTRA_ISSUES_REPO=demo/demo ORGESTRA_ISSUES_TOKEN=demo ORGESTRA_DB_PATH=$(mktemp -d)/demo.db ORGESTRA_RELOAD=0 uv run orgestra`), then `cd frontend && npm run demo -- --base http://127.0.0.1:8765 --out ../demo.mp4` (with `CHROMIUM_PATH` set to Chrome if Playwright's browser is missing). Stop the server afterwards. Do not submit the form against the real forge: the user does that check from their own terminal, where `direnv` exports the real variables.

- [ ] **Step 7: Stop and report**

Report what was built, the commits not yet pushed (including the earlier bubble and drawer fixes), and ask whether to push to PR #3, update its body and attach the new `demo.mp4`. Pushing and the PR update wait for the answer.

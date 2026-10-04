import json

import httpx2
import pytest

from orgestra.reports.build import build_tracker
from orgestra.reports.github import GitHubIssues
from orgestra.reports.tracker import Issue, TrackerError

TOKEN = "secret-token-123"  # noqa: S105 - a fake token the tests look for in output


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

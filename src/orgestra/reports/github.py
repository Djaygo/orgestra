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
        return Issue(number=issue_number(response))


def issue_number(response: httpx2.Response) -> int:
    try:
        number = response.json()["number"]
    except (ValueError, KeyError, TypeError) as error:
        raise TrackerError("GitHub answered 201 without an issue number") from error
    if not isinstance(number, int):
        raise TrackerError("GitHub answered 201 without an issue number")
    return number

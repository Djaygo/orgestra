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

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

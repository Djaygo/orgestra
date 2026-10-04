"""Line-based diffs between the revisions of a post."""

from __future__ import annotations

import difflib
from typing import Literal

import attrs

from orgestra.discussion.models import Post, Revision

DiffKind = Literal["add", "del", "same"]
MARKERS: dict[DiffKind, str] = {"add": "+", "del": "-", "same": " "}


@attrs.frozen
class DiffLine:
    kind: DiffKind
    text: str

    @property
    def marker(self) -> str:
        return MARKERS[self.kind]


@attrs.frozen
class HistoryEntry:
    revision: Revision
    lines: list[DiffLine]


def line_diff(old: str, new: str) -> list[DiffLine]:
    kinds: dict[str, DiffKind] = {"+ ": "add", "- ": "del", "  ": "same"}
    return [
        DiffLine(kinds[line[:2]], line[2:])
        for line in difflib.ndiff(old.splitlines(), new.splitlines())
        if line[:2] in kinds
    ]


def revision_history(post: Post) -> list[HistoryEntry]:
    """Every revision with its diff against the one before, newest first; the first is plain text."""
    entries: list[HistoryEntry] = []
    previous: Revision | None = None
    for revision in post.revisions:
        if previous is None:
            lines = [DiffLine("same", text) for text in revision.body.splitlines()]
        else:
            lines = line_diff(previous.body, revision.body)
        entries.append(HistoryEntry(revision, lines))
        previous = revision
    return entries[::-1]

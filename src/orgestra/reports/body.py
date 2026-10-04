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

"""Template filters for the discussion."""

from __future__ import annotations

import re
from datetime import datetime

from markupsafe import Markup, escape

from orgestra.discussion.models import utc_now

URL = re.compile(r"https?://[^\s<]+")
MINUTE, HOUR, DAY = 60, 3600, 86400


def ago(moment: datetime, now: datetime | None = None) -> str:
    seconds = ((now or utc_now()) - moment).total_seconds()
    if seconds < MINUTE:
        return "just now"
    if seconds < HOUR:
        return f"{int(seconds // MINUTE)} min ago"
    if seconds < DAY:
        return f"{int(seconds // HOUR)} h ago"
    return f"{int(seconds // DAY)} d ago"


def linkify(text: str) -> Markup:
    """Escape the text, then turn bare http(s) URLs into links. Line breaks are left to CSS."""
    escaped = str(escape(text))
    linked = URL.sub(lambda m: f'<a href="{m[0]}" rel="nofollow noopener">{m[0]}</a>', escaped)
    return Markup(linked)  # noqa: S704 - built from escaped text and links around escaped URLs

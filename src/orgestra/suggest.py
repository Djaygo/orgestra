"""Predictions for the search box: topics, speakers and talk titles that match what was typed so far."""

from __future__ import annotations

import re
from typing import Literal
from urllib.parse import quote

import attrs

from orgestra.dataset import Catalog

MIN_CHARS = 2
# Equal matches list topics first (short and broad), then speakers, then talks.
KIND_ORDER = {"topic": 0, "speaker": 1, "talk": 2}
SPEAKERS_SHOWN = 2


@attrs.frozen
class Suggestion:
    kind: Literal["talk", "speaker", "topic"]
    label: str
    href: str
    detail: str


def match_rank(label: str, needle: str) -> int | None:
    """0 for a prefix, 1 for the start of a later word, 2 for anywhere else, None for no match."""
    text = label.casefold()
    if text.startswith(needle):
        return 0
    if re.search(r"(?<!\w)" + re.escape(needle), text):
        return 1
    return 2 if needle in text else None


def candidates(catalog: Catalog) -> list[Suggestion]:
    found = [Suggestion("topic", tag, f"/search?q={quote(tag)}", "Topic") for tag, _ in catalog.tag_counts()]
    found += [
        Suggestion("speaker", speaker.name, f"/speakers/{speaker.slug}", speaker.role_company or "Speaker")
        for speaker in catalog.speakers.values()
    ]
    for talk in catalog.talks.values():
        if talk.title:
            names = ", ".join(speaker.name for speaker in talk.speakers[:SPEAKERS_SHOWN])
            found.append(
                Suggestion("talk", talk.title, f"/talks/{talk.ref}", f"{talk.year} · {names}".rstrip(" ·"))
            )
    return found


def suggest(catalog: Catalog, query: str, limit: int = 6) -> list[Suggestion]:
    needle = " ".join(query.casefold().split())
    if len(needle) < MIN_CHARS:
        return []
    ranked = [
        ((rank, KIND_ORDER[found.kind], found.label.casefold()), found)
        for found in candidates(catalog)
        if (rank := match_rank(found.label, needle)) is not None
    ]
    return [found for _, found in sorted(ranked, key=lambda pair: pair[0])[:limit]]

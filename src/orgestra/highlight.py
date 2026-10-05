"""Marking the words a search matched."""

from __future__ import annotations

import re
from collections.abc import Iterable

from markupsafe import Markup, escape

from orgestra.text import stem

TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9#+]*")


def highlight(text: str, words: Iterable[str]) -> Markup:
    """The text escaped, with every word whose stem is one of `words` wrapped in <mark>.

    Words are compared the way the index compares them (lowercased and stemmed), so "tests" is marked
    for a search for "testing". The text is cut around the matches before it is escaped, so markup in
    the text or an entity made by escaping is never marked.
    """
    wanted = frozenset(words)
    parts: list[Markup] = []
    end = 0
    for match in TOKEN.finditer(text):
        if stem(match[0].lower()) in wanted:
            parts += [
                escape(text[end : match.start()]),
                Markup("<mark>"),
                escape(match[0]),
                Markup("</mark>"),
            ]
            end = match.end()
    parts.append(escape(text[end:]))
    return Markup("").join(parts)

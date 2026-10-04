"""Tokenizing and light stemming shared by the index, the thesaurus and the query."""

from __future__ import annotations

import re
from typing import TypeAlias

Terms: TypeAlias = tuple[str, ...]

WORD = re.compile(r"[a-z0-9][a-z0-9#+]*")
# (suffix, replacement, minimum word length for the rule to apply), first match wins.
SUFFIX_RULES = (
    ("ies", "y", 5),
    ("sses", "ss", 5),
    ("ing", "", 6),
    ("ed", "", 5),
    ("s", "", 4),
)
UNSTEMMED_ENDINGS = ("ss", "us", "is")


def stem(word: str) -> str:
    """Strip common English inflections so "tests", "testing" and "tested" meet at "test"."""
    if word.endswith(UNSTEMMED_ENDINGS):
        return word
    for suffix, replacement, min_length in SUFFIX_RULES:
        if word.endswith(suffix) and len(word) >= min_length:
            return word[: -len(suffix)] + replacement
    return word


def terms(text: str) -> Terms:
    """Lowercase, split on anything that is not a word character, stem."""
    return tuple(stem(word) for word in WORD.findall(text.lower().replace("'s", "")))

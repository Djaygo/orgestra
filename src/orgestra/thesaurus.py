"""Expand a query into concepts: each word or phrase plus the terms that mean the same thing."""

from __future__ import annotations

import tomllib
from importlib import resources
from typing import TypeAlias

import attrs

from orgestra.text import Terms, terms

# Every way of saying one thing, each already split into terms.
SynonymGroup: TypeAlias = frozenset[Terms]
GroupIndexes: TypeAlias = tuple[int, ...]
# One group as written in thesaurus.toml.
RawGroup: TypeAlias = list[str]


@attrs.frozen
class Concept:
    """One thing the user asked for: the words they typed and every way of saying it."""

    label: str
    variants: frozenset[Terms]

    @property
    def alternatives(self) -> list[str]:
        """The variants other than what was typed, for showing "also searched for"."""
        typed = terms(self.label)
        return sorted(" ".join(variant) for variant in self.variants if variant != typed)


@attrs.frozen
class Thesaurus:
    groups: tuple[SynonymGroup, ...]
    # variant -> indexes of the groups it belongs to
    lookup: dict[Terms, GroupIndexes]
    longest: int

    @classmethod
    def from_groups(cls, groups: list[RawGroup]) -> Thesaurus:
        parsed = tuple(frozenset(terms(word) for word in group if terms(word)) for group in groups)
        lookup: dict[Terms, GroupIndexes] = {}
        for index, group in enumerate(parsed):
            for variant in group:
                lookup[variant] = (*lookup.get(variant, ()), index)
        return cls(groups=parsed, lookup=lookup, longest=max((len(v) for v in lookup), default=1))

    def synonyms(self, variant: Terms) -> frozenset[Terms]:
        found = {variant}
        for index in self.lookup.get(variant, ()):
            found |= self.groups[index]
        return frozenset(found)

    def expand(self, query: str) -> list[Concept]:
        """Split a query into concepts, preferring the longest phrase the thesaurus knows."""
        words = query.lower().split()
        stems = [terms(word) for word in words]
        concepts: list[Concept] = []
        position = 0
        while position < len(words):
            size = self._phrase_length(stems, position)
            phrase: Terms = tuple(t for word in stems[position : position + size] for t in word)
            if phrase:
                label = " ".join(words[position : position + size])
                concepts.append(Concept(label=label, variants=self.synonyms(phrase)))
            position += size
        return concepts

    def _phrase_length(self, stems: list[Terms], position: int) -> int:
        for size in range(min(self.longest, len(stems) - position), 1, -1):
            phrase = tuple(t for word in stems[position : position + size] for t in word)
            if phrase in self.lookup:
                return size
        return 1


def load_thesaurus() -> Thesaurus:
    source = resources.files("orgestra.resources").joinpath("thesaurus.toml").read_text(encoding="utf-8")
    return Thesaurus.from_groups(tomllib.loads(source)["groups"])

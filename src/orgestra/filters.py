"""The filters of the results page: a year, talks with slides, talks with video."""

from __future__ import annotations

from urllib.parse import quote

import attrs

from orgestra.dataset import Talk

YEAR_DIGITS = 4


@attrs.frozen
class Filters:
    year: int | None = None
    slides: bool = False
    video: bool = False

    @classmethod
    def parse(cls, year: str, slides: str, video: str) -> Filters:
        """Anything that is not a four-digit year or "1" is ignored."""
        return cls(
            year=int(year) if year.isascii() and year.isdigit() and len(year) == YEAR_DIGITS else None,
            slides=slides == "1",
            video=video == "1",
        )

    @property
    def active(self) -> bool:
        return self != Filters()

    def keeps(self, talk: Talk) -> bool:
        return (
            self.year in (None, talk.year)
            and (not self.slides or talk.has_slides)
            and (not self.video or talk.has_video)
        )

    def url(self, query: str, **changes: int | bool | None) -> str:
        """The results URL for this query with these filters, after applying `changes`."""
        filters = attrs.evolve(self, **changes)
        parts = [f"q={quote(query)}"]
        if filters.year:
            parts.append(f"year={filters.year}")
        if filters.slides:
            parts.append("slides=1")
        if filters.video:
            parts.append("video=1")
        return "/search?" + "&".join(parts)

"""The presentation rooms along the top of the expo hall: the busiest rooms of the newest year."""

from __future__ import annotations

from collections import Counter

import attrs

from orgestra.dataset import Catalog, Talk

ROOM_COUNT = 3
VENUE_PREFIX = "TAP1, "  # the venue GOTO Copenhagen names before each room


@attrs.frozen
class Room:
    name: str
    talks: list[Talk]

    @property
    def showing(self) -> str:
        """The title on the room's screen: its first talk with slides, else its first talk."""
        with_slides = [talk for talk in self.talks if talk.has_slides]
        first = (with_slides or self.talks)[0] if self.talks else None
        return first.display_title if first else ""


def display_name(room: str) -> str:
    return room.removeprefix(VENUE_PREFIX)


def rooms(catalog: Catalog) -> list[Room]:
    years = catalog.stats().years
    if not years:
        return []
    talks = [talk for talk in catalog.talks.values() if talk.year == years[0] and talk.room and talk.title]
    busiest = Counter(room for talk in talks if (room := talk.room)).most_common(ROOM_COUNT)
    return [
        Room(
            display_name(name),
            sorted(
                (talk for talk in talks if talk.room == name),
                key=lambda talk: (talk.day or "", talk.start or ""),
            ),
        )
        for name, _count in busiest
    ]

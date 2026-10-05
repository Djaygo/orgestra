"""Load the conference dataset from data/<organization>/ into one in-memory catalog.

The JSON files are parsed into pydantic models where they enter; the rest of the app reads the
`Catalog`. Layout: see data/gotocph/README.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypeAlias

import attrs
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TalkSpeaker(BaseModel):
    model_config = ConfigDict(frozen=True)

    slug: str
    name: str
    role_company: str | None = None


PENDING_SLIDES = "__PENDING__"


class Talk(BaseModel):
    """One talk.json: schedule entry, abstract and links."""

    model_config = ConfigDict(frozen=True)

    slug: str
    organization: str
    year: int
    session_id: int
    extracted: bool = False
    title: str | None = None
    section: str | None = None
    formats: list[str] = Field(default_factory=list, alias="format")
    track: str | None = None
    tags: list[str] = Field(default_factory=list)
    day: str | None = None
    start: str | None = None
    end: str | None = None
    room: str | None = None
    abstract: str | None = None
    speakers: list[TalkSpeaker] = Field(default_factory=list)
    session_url: str
    video_url: str | None = None
    other_links: list[str] = Field(default_factory=list)
    slides_url: str | None = None
    slides_file: str | None = None

    @field_validator("slides_url", mode="after")
    @classmethod
    def _no_placeholder(cls, value: str | None) -> str | None:
        """The schedule extraction left "__PENDING__" where no deck was uploaded yet."""
        return None if value == PENDING_SLIDES else value

    @field_validator("formats", mode="before")
    @classmethod
    def _formats_as_list(cls, value: object) -> object:
        """The schedule gives one format ("Keynote") or several ("Slides", "Code examples")."""
        if value is None:
            return []
        return [value] if isinstance(value, str) else value

    @property
    def ref(self) -> str:
        """Stable id used in URLs and in speaker files: `<year>/<slug>`."""
        return f"{self.year}/{self.slug}"

    @property
    def display_title(self) -> str:
        return self.title or self.slug.replace("-", " ").capitalize()


class Speaker(BaseModel):
    """One speakers/<slug>.json: the persona and how to reach them."""

    model_config = ConfigDict(frozen=True)

    slug: str
    name: str
    role_company: str | None = None
    role: str | None = None
    company: str | None = None
    bio: str | None = None
    email: str | None = None
    photo_url: str | None = None
    links: dict[str, str] = Field(default_factory=dict)
    profiles: dict[str, str] = Field(default_factory=dict)
    talks: list[str] = Field(default_factory=list)


class Edition(BaseModel):
    model_config = ConfigDict(frozen=True)

    year: int
    talks: int
    extracted: int = 0
    slides_known: int = 0
    slides_downloaded: int = 0


class Organization(BaseModel):
    """The top-level index.json of one conference."""

    model_config = ConfigDict(frozen=True)

    slug: str
    name: str
    url: str
    editions: list[Edition] = Field(default_factory=list)


TalksByYear: TypeAlias = dict[int, list[Talk]]


@attrs.frozen
class OrganizationData:
    organization: Organization
    talks: list[Talk]
    speakers: list[Speaker]


@attrs.frozen
class Catalog:
    """Everything the app knows about, keyed for lookup."""

    organizations: list[Organization]
    talks: dict[str, Talk]
    speakers: dict[str, Speaker]

    def talks_by_year(self, organization: str) -> TalksByYear:
        by_year: TalksByYear = {}
        for talk in self.talks.values():
            if talk.organization == organization:
                by_year.setdefault(talk.year, []).append(talk)
        for talks in by_year.values():
            talks.sort(key=lambda talk: (not talk.extracted, talk.display_title.lower()))
        return dict(sorted(by_year.items(), reverse=True))

    def speakers_of(self, talk: Talk) -> list[Speaker]:
        return [self.speakers[s.slug] for s in talk.speakers if s.slug in self.speakers]

    def talks_of(self, speaker: Speaker) -> list[Talk]:
        return [self.talks[ref] for ref in speaker.talks if ref in self.talks]


def load_organization(root: Path) -> OrganizationData:
    organization = Organization.model_validate_json((root / "index.json").read_text(encoding="utf-8"))
    talks = [
        Talk.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(root.glob("*/*/talk.json"))
    ]
    speakers = [
        Speaker.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted((root / "speakers").glob("*.json"))
    ]
    return OrganizationData(organization=organization, talks=talks, speakers=speakers)


def load_catalog(data_dir: Path) -> Catalog:
    """Read every data/<organization>/ that has an index.json."""
    organizations: list[Organization] = []
    talks: dict[str, Talk] = {}
    speakers: dict[str, Speaker] = {}
    for root in sorted(path.parent for path in data_dir.glob("*/index.json")):
        loaded = load_organization(root)
        organizations.append(loaded.organization)
        talks.update((talk.ref, talk) for talk in loaded.talks)
        speakers.update((speaker.slug, speaker) for speaker in loaded.speakers)
    return Catalog(organizations=organizations, talks=talks, speakers=speakers)

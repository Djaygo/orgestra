from __future__ import annotations

from typing import Any

import pytest

from orgestra.dataset import Catalog, Organization, Speaker, Talk
from orgestra.discussion.models import db
from orgestra.thesaurus import Thesaurus, load_thesaurus


def make_talk(slug: str, **fields: Any) -> Talk:
    defaults: dict[str, Any] = {
        "organization": "conf",
        "year": 2025,
        "session_id": abs(hash(slug)) % 10_000,
        "extracted": True,
        "title": slug.replace("-", " ").title(),
        "session_url": f"https://example.com/{slug}",
    }
    return Talk(slug=slug, **(defaults | fields))


@pytest.fixture
def catalog() -> Catalog:
    talks = [
        make_talk(
            "kubernetes-at-scale",
            title="Kubernetes at Scale",
            tags=["platforms"],
            abstract="Why do clusters fall over? Because nobody owns them. We show how teams run k8s.",
            speakers=[{"slug": "ada", "name": "Ada Lovelace"}],
        ),
        make_talk(
            "llms-in-production",
            title="Large Language Models in Production",
            tags=["AI", "platforms"],
            abstract="Shipping a chatbot is easy. Keeping it honest is not.",
            speakers=[{"slug": "grace", "name": "Grace Hopper"}],
        ),
        make_talk("unknown-talk", extracted=False, title=None),
        make_talk("kubernetes-unplugged", extracted=False, title=None),
    ]
    speakers = [
        Speaker(slug="ada", name="Ada Lovelace", talks=["2025/kubernetes-at-scale"]),
        Speaker(
            slug="grace", name="Grace Hopper", email="grace@example.com", talks=["2025/llms-in-production"]
        ),
    ]
    organization = Organization(slug="conf", name="Conf", url="https://example.com")
    return Catalog(
        organizations=[organization],
        talks={talk.ref: talk for talk in talks},
        speakers={speaker.slug: speaker for speaker in speakers},
    )


@pytest.fixture(scope="session")
def thesaurus() -> Thesaurus:
    return load_thesaurus()


@pytest.fixture
def session(tmp_path):
    """A session on a fresh database file (an in-memory database is per thread)."""
    db.initialize(f"sqlite:///{tmp_path / 'test.db'}")
    db.create_all()
    with db.begin() as session:
        yield session

import pytest

from orgestra.dataset import Catalog, CatalogStats
from tests.conftest import make_talk


@pytest.mark.parametrize(
    ("given", "expected"),
    [("__PENDING__", None), (None, None), ("https://x.test/a.pdf", "https://x.test/a.pdf")],
)
def test_a_pending_slides_placeholder_is_no_slides(given, expected):
    assert make_talk("t", slides_url=given).slides_url == expected


def test_popular_tags_are_the_most_used_first_then_alphabetical(catalog):
    assert catalog.popular_tags(limit=2) == ["platforms", "AI"]


def test_popular_tags_skip_blank_tags_and_respect_the_limit(catalog):
    assert len(catalog.popular_tags(limit=1)) == 1
    assert "" not in catalog.popular_tags(limit=10)


def test_tags_differing_only_in_case_are_one_topic_in_their_most_common_spelling():
    catalog = Catalog(
        organizations=[],
        talks={
            "2025/a": make_talk("a", tags=["AI agents", "security"]),
            "2025/b": make_talk("b", tags=["AI agents"]),
            "2025/c": make_talk("c", tags=["AI Agents", "ai agents"]),
        },
        speakers={},
    )

    assert catalog.tag_counts() == [("AI agents", 4), ("security", 1)]
    assert catalog.popular_tags(limit=1) == ["AI agents"]


def test_stats_count_talks_speakers_slides_videos_and_years(catalog):
    assert catalog.stats() == CatalogStats(talks=4, speakers=2, with_slides=0, with_video=0, years=[2025])

    with_media = Catalog(
        organizations=[],
        talks={
            "2026/a": make_talk(
                "a", year=2026, slides_url="https://x.test/a.pdf", video_url="https://x.test/v"
            ),
            "2025/b": make_talk("b", year=2025, slides_url="__PENDING__"),
        },
        speakers={},
    )
    assert with_media.stats() == CatalogStats(
        talks=2, speakers=0, with_slides=1, with_video=1, years=[2026, 2025]
    )

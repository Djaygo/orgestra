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


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube-nocookie.com/embed/ZTfnRXtIFEo",
        "https://player.vimeo.com/video/1084537",
        "https://player.vimeo.com/video/1084537?h=abc123def",
    ],
)
def test_the_two_known_players_become_embeds(url):
    assert make_talk("t", video_url=url).embed_url == url


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        "https://www.youtube.com/embed/ZTfnRXtIFEo",
        "https://youtube-nocookie.com.evil.test/embed/ZTfnRXtIFEo",
        "https://evil.test/https://www.youtube-nocookie.com/embed/x",
        "http://www.youtube-nocookie.com/embed/ZTfnRXtIFEo",
        "https://player.vimeo.com@evil.test/video/1",
        "https://user:pass@player.vimeo.com/video/1",
        "https://player.vimeo.com:8443/video/1",
        "https://player.vimeo.com:abc/video/1",
        "https://[player.vimeo.com/video/1",
        "https://www.youtube-nocookie.com/watch?v=ZTfnRXtIFEo",
        "https://www.youtube-nocookie.com/embed/",
        "https://www.youtube-nocookie.com/embed/../x",
        "https://www.youtube-nocookie.com/embed/a/b",
        "javascript:alert(1)",
    ],
)
def test_anything_else_is_not_embedded(url):
    assert make_talk("t", video_url=url).embed_url is None


def test_related_talks_share_tags_best_first_and_never_include_the_talk_itself():
    talk = make_talk("main", year=2025, tags=["ai", "testing"])
    catalog = Catalog(
        organizations=[],
        talks={
            t.ref: t
            for t in [
                talk,
                make_talk("both", year=2025, tags=["AI", "Testing"], title="Both tags"),
                make_talk("one-new", year=2026, tags=["ai"], title="One tag newer"),
                make_talk("one-same", year=2025, tags=["ai"], title="One tag same year"),
                make_talk("none", year=2025, tags=["cooking"]),
                make_talk("pending", year=2025, tags=["ai", "testing"], extracted=False),
            ]
        },
        speakers={},
    )

    assert [t.slug for t in catalog.related(talk)] == ["both", "one-same", "one-new"]
    assert [t.slug for t in catalog.related(talk, limit=1)] == ["both"]


def test_a_talk_without_tags_has_no_related_talks():
    talk = make_talk("main", tags=[])
    catalog = Catalog(
        organizations=[], talks={talk.ref: talk, "2025/x": make_talk("x", tags=["ai"])}, speakers={}
    )

    assert catalog.related(talk) == []

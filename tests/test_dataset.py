import pytest

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

import pytest

from tests.conftest import make_talk


@pytest.mark.parametrize(
    ("given", "expected"),
    [("__PENDING__", None), (None, None), ("https://x.test/a.pdf", "https://x.test/a.pdf")],
)
def test_a_pending_slides_placeholder_is_no_slides(given, expected):
    assert make_talk("t", slides_url=given).slides_url == expected

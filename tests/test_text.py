import pytest

from orgestra.text import stem, terms


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("tests", "test"),
        ("testing", "test"),
        ("tested", "test"),
        ("libraries", "library"),
        ("class", "class"),
        ("status", "status"),
        ("is", "is"),
        ("ai", "ai"),
    ],
)
def test_stem(word, expected):
    assert stem(word) == expected


def test_terms_lowercases_splits_and_drops_possessives():
    assert terms("Kubernetes' Testing, Martin's C# talk") == ("kubernete", "test", "martin", "c#", "talk")

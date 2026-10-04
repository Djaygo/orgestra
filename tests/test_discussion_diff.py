from datetime import datetime, timedelta

from orgestra.discussion.diff import DiffLine, line_diff, revision_history
from orgestra.discussion.render import ago, linkify
from orgestra.discussion.store import add_post, edit_post


def test_line_diff_marks_added_removed_and_unchanged_lines():
    lines = line_diff("a\nb\nc", "a\nB\nc\nd")

    assert lines == [
        DiffLine("same", "a"),
        DiffLine("del", "b"),
        DiffLine("add", "B"),
        DiffLine("same", "c"),
        DiffLine("add", "d"),
    ]
    assert [line.marker for line in lines] == [" ", "-", "+", " ", "+"]


def test_history_is_newest_first_with_the_original_as_plain_text(session):
    post = add_post(session, "2025/a", "comment", "Ada", "one\ntwo")
    edit_post(session, post, "Bob", "one\n2")

    newest, original = revision_history(post)

    assert newest.revision.editor_name == "Bob"
    assert [(line.kind, line.text) for line in newest.lines] == [
        ("same", "one"),
        ("del", "two"),
        ("add", "2"),
    ]
    assert {line.kind for line in original.lines} == {"same"}


def test_ago_picks_the_largest_unit():
    now = datetime(2026, 10, 4, 12, 0)
    assert ago(now - timedelta(seconds=20), now) == "just now"
    assert ago(now - timedelta(minutes=3), now) == "3 min ago"
    assert ago(now - timedelta(hours=5), now) == "5 h ago"
    assert ago(now - timedelta(days=2), now) == "2 d ago"


def test_linkify_escapes_markup_and_links_urls():
    html = str(linkify('<b>hi</b> see https://example.com/?a=1&b=2 "now"'))

    assert "<b>" not in html
    assert "&lt;b&gt;hi&lt;/b&gt;" in html
    assert 'href="https://example.com/?a=1&amp;b=2"' in html
    assert 'rel="nofollow noopener"' in html

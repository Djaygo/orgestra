import pytest

from orgestra.discussion.store import (
    add_post,
    add_reply,
    edit_post,
    restore_revision,
    talk_stats,
    thread,
    toggle_answered,
)

TALK = "2025/a"


def test_thread_nests_replies_and_lists_newest_first(session):
    first = add_post(session, TALK, "comment", "Ada", "first")
    second = add_post(session, TALK, "question", "Bob", "second?")
    reply = add_reply(session, first, "Cy", "reply")
    add_reply(session, reply, "Di", "nested")
    add_post(session, "2025/b", "comment", "Eve", "other talk")

    top = thread(session, TALK)

    assert [post.id for post in top] == [second.id, first.id]
    assert top[1].replies[0].replies[0].body == "nested"
    assert top[1].thread_size == 3
    assert reply.kind == "comment"
    assert reply.talk_ref == TALK


def test_edits_append_revisions_and_the_latest_is_the_text(session):
    post = add_post(session, TALK, "comment", "Ada", "one")

    revision = edit_post(session, post, "Bob", "two")

    assert revision is not None
    assert post.body == "two"
    assert post.edited
    assert [r.editor_name for r in post.revisions] == ["Ada", "Bob"]


def test_unchanged_text_adds_no_revision(session):
    post = add_post(session, TALK, "comment", "Ada", "one")

    assert edit_post(session, post, "Bob", "one") is None
    assert not post.edited


def test_restore_appends_a_revision_with_the_old_text(session):
    post = add_post(session, TALK, "comment", "Ada", "one")
    edit_post(session, post, "Bob", "two")
    original = post.revisions[0]

    restore_revision(session, post, original.id, "Cy")

    assert post.body == "one"
    assert len(post.revisions) == 3
    assert post.latest.editor_name == "Cy"


def test_restoring_the_current_version_adds_nothing(session):
    post = add_post(session, TALK, "comment", "Ada", "one")
    edit_post(session, post, "Bob", "two")

    assert restore_revision(session, post, post.latest.id, "Cy") is None
    assert len(post.revisions) == 2


def test_restoring_a_revision_of_another_post_fails(session):
    post = add_post(session, TALK, "comment", "Ada", "one")
    other = add_post(session, TALK, "comment", "Bob", "other")

    with pytest.raises(LookupError):
        restore_revision(session, post, other.latest.id, "Cy")


def test_answered_toggles_on_questions_only(session):
    question = add_post(session, TALK, "question", "Ada", "why?")
    comment = add_post(session, TALK, "comment", "Bob", "hm")

    toggle_answered(question)
    assert question.answered
    toggle_answered(question)
    assert not question.answered
    with pytest.raises(ValueError, match="question"):
        toggle_answered(comment)


def test_talk_stats_count_posts_and_last_activity(session):
    post = add_post(session, TALK, "comment", "Ada", "one")
    add_reply(session, post, "Bob", "two")
    add_post(session, "2025/b", "comment", "Eve", "other")

    stats = talk_stats(session, [TALK, "2025/b", "2025/none"])

    assert stats[TALK].posts == 2
    assert stats["2025/b"].posts == 1
    assert "2025/none" not in stats
    assert stats[TALK].last_activity >= post.created_at

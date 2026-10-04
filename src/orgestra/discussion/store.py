"""Discussion reads and writes on a session. Knows nothing about HTTP."""

from __future__ import annotations

from datetime import datetime

import attrs
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from orgestra.discussion.models import Kind, Post, Revision


@attrs.frozen
class TalkStats:
    """What the result list shows per talk."""

    posts: int
    last_activity: datetime


def add_post(session: Session, talk_ref: str, kind: Kind, author: str, body: str) -> Post:
    post = Post(
        talk_ref=talk_ref,
        kind=kind,
        author_name=author,
        revisions=[Revision(body=body, editor_name=author)],
    )
    session.add(post)
    session.flush()
    return post


def add_reply(session: Session, parent: Post, author: str, body: str) -> Post:
    reply = Post(
        talk_ref=parent.talk_ref,
        kind="comment",
        author_name=author,
        revisions=[Revision(body=body, editor_name=author)],
    )
    parent.replies.append(reply)
    session.flush()
    return reply


def edit_post(session: Session, post: Post, editor: str, body: str) -> Revision | None:
    """Append a revision; unchanged text adds nothing."""
    if body == post.body:
        return None
    revision = Revision(body=body, editor_name=editor)
    post.revisions.append(revision)
    session.flush()
    return revision


def restore_revision(session: Session, post: Post, revision_id: int, editor: str) -> Revision | None:
    """Append a revision with an earlier text of this post; nothing is ever deleted."""
    chosen = next((r for r in post.revisions if r.id == revision_id), None)
    if chosen is None:
        raise LookupError(f"post {post.id} has no revision {revision_id}")
    return edit_post(session, post, editor, chosen.body)


def toggle_answered(post: Post) -> None:
    if post.kind != "question":
        raise ValueError("only a question can be answered")
    post.answered = not post.answered


def thread(session: Session, talk_ref: str) -> list[Post]:
    """Top-level posts of a talk, newest first; replies hang off `Post.replies`."""
    top_level = select(Post).where(Post.talk_ref == talk_ref, Post.parent_id.is_(None))
    return list(session.scalars(top_level.order_by(Post.id.desc())))


def talk_stats(session: Session, refs: list[str]) -> dict[str, TalkStats]:
    rows = session.execute(
        select(Post.talk_ref, func.count(distinct(Post.id)), func.max(Revision.created_at))
        .join(Revision, Revision.post_id == Post.id)
        .where(Post.talk_ref.in_(refs))
        .group_by(Post.talk_ref)
    )
    return {ref: TalkStats(posts=posts, last_activity=last) for ref, posts, last in rows}

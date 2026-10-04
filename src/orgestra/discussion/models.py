"""Discussion data: posts form a tree per talk, and each post is a list of revisions.

The text of a post is its latest revision; the first revision is the original post.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from alchemical import Alchemical
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

db = Alchemical()

Kind = Literal["comment", "question"]


def utc_now() -> datetime:
    """Naive UTC, the form SQLite stores and every comparison here uses."""
    return datetime.now(UTC).replace(tzinfo=None)


class Post(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    talk_ref: Mapped[str] = mapped_column(index=True)  # "<year>/<slug>", the catalog key
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("post.id"))  # None for a top-level post
    kind: Mapped[str]
    author_name: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    answered: Mapped[bool] = mapped_column(default=False)  # questions only
    revisions: Mapped[list[Revision]] = relationship(order_by="Revision.id")
    replies: Mapped[list[Post]] = relationship(order_by="Post.id")

    @property
    def latest(self) -> Revision:
        return self.revisions[-1]

    @property
    def body(self) -> str:
        return self.latest.body

    @property
    def edited(self) -> bool:
        return len(self.revisions) > 1

    @property
    def thread_size(self) -> int:
        return 1 + sum(reply.thread_size for reply in self.replies)


class Revision(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("post.id"), index=True)
    body: Mapped[str]
    editor_name: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

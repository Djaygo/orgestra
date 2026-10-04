# Talk Discussion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Visitors discuss each talk in a nested comment and question tree stored in SQLite, anyone can edit any post with line-diff history, and search results and the talk page take on a forum look.

**Architecture:** A `discussion` package holds SQLAlchemy models (through alchemical), a session-based store, a diff module, template filters and form routes. Every mutation is a plain form POST that redirects (303) back to the talk page; `<details>` elements give inline reply, edit and history, and the existing `hx-boost` swaps pages in place. The talk catalog stays in JSON; the database holds discussion data only.

**Tech Stack:** FastAPI, Jinja2, alchemical (SQLAlchemy 2.0) on SQLite, python-multipart for forms, pytest, ruff, ty.

**Spec:** `docs/superpowers/specs/2026-10-04-talk-discussion-design.md`

## Global Constraints

- Add dependencies only with `uv add` (never edit `pyproject.toml` by hand): `alchemical` and `python-multipart`.
- Python 3.11+, line length 110, ruff and ty must pass (`uv run ruff check`, `uv run ruff format --check`, `uv run ty check`).
- Database file: `data/orgestra.db`, set by `ORGESTRA_DB_PATH`, gitignored. Tests always pass a `db_path` under `tmp_path`, never the repo `data/` directory.
- The text of a post is its latest revision; edit count, "edited", reply counts and talk stats are derived, never stored.
- No spam protection, no edit-conflict handling, no moderation, no accounts.
- Body 1 to 5000 characters and name 1 to 40 characters after trimming; the server answers 422 and stores nothing otherwise.
- Output is HTML-escaped by Jinja; URLs become links with `rel="nofollow noopener"`.
- Comments: describe the current state only; never remove existing comments or docstrings.
- Commits end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; plain imperative style, no amending, no force-push.

## Review Focus

- A body containing `<script>` or `&` must render escaped, never as markup (test in Task 4).
- A whitespace-only body or name must be rejected with 422 and store nothing (Task 4).
- A reply to, edit of, restore on or answered toggle of a post that does not exist, and a post on an unknown talk, must be 404 (Task 4).
- A non-ASCII display name (`Zoë`) must come back unchanged from the remembered-name cookie (Task 4).
- Saving an edit with unchanged text must not add a revision, and restoring the current version must not either (Task 2).

## File Structure

| File | Responsibility |
|---|---|
| `src/orgestra/discussion/__init__.py` | package marker |
| `src/orgestra/discussion/models.py` | `db`, `Post`, `Revision`, `utc_now` |
| `src/orgestra/discussion/store.py` | session functions: add, reply, edit, restore, answered, thread, stats |
| `src/orgestra/discussion/diff.py` | `DiffLine`, `line_diff`, `HistoryEntry`, `revision_history` |
| `src/orgestra/discussion/render.py` | `ago` and `linkify` template filters |
| `src/orgestra/discussion/routes.py` | form models, routes, remembered-name cookie |
| `src/orgestra/templates/partials/discussion/section.html`, `post.html` | discussion UI |
| `src/orgestra/templates/talk.html`, `partials/results.html` | include the discussion; forum-style result rows |
| `src/orgestra/static/css/app.css` | discussion and topic-list styles |
| `src/orgestra/app.py` | settings, db init, filters, router, talk and search context |
| `tests/test_discussion_*.py` | store, diff and render, routes |
| `frontend/scripts/record-demo.mjs` | demo step for the discussion |

---

### Task 1: Dependencies, models and database wiring

**Files:**
- Modify: `pyproject.toml`, `uv.lock` (through `uv add`), `.gitignore`, `src/orgestra/app.py`, `tests/test_app.py`, `tests/conftest.py`
- Create: `src/orgestra/discussion/__init__.py`, `src/orgestra/discussion/models.py`

**Interfaces:**
- Produces: `orgestra.discussion.models.db` (an `Alchemical()`), `Post`, `Revision`, `Kind = Literal["comment", "question"]`, `utc_now() -> datetime` (naive UTC); `Settings.db_path: Path`; a `session` pytest fixture yielding a `sqlalchemy.orm.Session` on a fresh file database.
- `Post` properties: `latest -> Revision`, `body -> str`, `edited -> bool`, `thread_size -> int` (this post plus all descendants).

- [ ] **Step 1: Add the dependencies**

Run: `uv add alchemical python-multipart`
Expected: both appear in `pyproject.toml` dependencies and `uv.lock` updates.

- [ ] **Step 2: Gitignore the database**

Append to `.gitignore`:

```
# Discussion database
data/orgestra.db*
```

- [ ] **Step 3: Write the models**

Create empty `src/orgestra/discussion/__init__.py`, then `src/orgestra/discussion/models.py`:

```python
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
```

- [ ] **Step 4: Wire settings and startup in `src/orgestra/app.py`**

Add the import `from orgestra.discussion.models import db`. Replace `Settings` with:

```python
@attrs.frozen
class Settings:
    data_dir: Path = REPO_DATA_DIR
    db_path: Path = REPO_DATA_DIR / "orgestra.db"
    turn_interval_s: float = 3.5

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            data_dir=Path(os.environ.get("ORGESTRA_DATA_DIR", REPO_DATA_DIR)),
            db_path=Path(os.environ.get("ORGESTRA_DB_PATH", REPO_DATA_DIR / "orgestra.db")),
            turn_interval_s=float(os.environ.get("ORGESTRA_TURN_INTERVAL", "3.5")),
        )
```

In `create_app`, before building services:

```python
    resolved = settings or Settings.from_env()
    resolved.db_path.parent.mkdir(parents=True, exist_ok=True)
    db.initialize(f"sqlite:///{resolved.db_path}")
    db.create_all()
    app.state.services = build_services(resolved)
```
(remove the old `app.state.services = build_services(settings or Settings.from_env())` line).

- [ ] **Step 5: Keep the existing app tests off the repo database**

In `tests/test_app.py` change the fixture to:

```python
@pytest.fixture(scope="module")
def client(tmp_path_factory):
    # The dataset checked in under data/ is the fixture for the routes; the database is a throwaway.
    db_path = tmp_path_factory.mktemp("db") / "orgestra.db"
    return TestClient(create_app(Settings(data_dir=REPO_DATA_DIR, db_path=db_path)))
```

- [ ] **Step 6: Add the `session` fixture to `tests/conftest.py`**

```python
from orgestra.discussion.models import db


@pytest.fixture
def session(tmp_path):
    """A session on a fresh database file (an in-memory database is per thread)."""
    db.initialize(f"sqlite:///{tmp_path / 'test.db'}")
    db.create_all()
    with db.begin() as session:
        yield session
```

- [ ] **Step 7: Verify nothing broke and the schema builds**

Run: `uv run pytest -q && uv run ruff check && uv run ruff format --check && uv run ty check`
Expected: all existing tests pass; no lint, format or type errors. If `ty` rejects the SQLAlchemy `Mapped` annotations, fix the annotations (not by silencing) and re-run.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock .gitignore src/orgestra tests
git commit -m "Add the discussion models and a SQLite database next to the app"
```

---

### Task 2: Store

**Files:**
- Create: `src/orgestra/discussion/store.py`
- Test: `tests/test_discussion_store.py`

**Interfaces:**
- Consumes: `Post`, `Revision`, `Kind`, `session` fixture (Task 1).
- Produces (all take a `sqlalchemy.orm.Session` first):
  - `add_post(session, talk_ref: str, kind: Kind, author: str, body: str) -> Post`
  - `add_reply(session, parent: Post, author: str, body: str) -> Post`
  - `edit_post(session, post: Post, editor: str, body: str) -> Revision | None` (None when the text is unchanged)
  - `restore_revision(session, post: Post, revision_id: int, editor: str) -> Revision | None` (raises `LookupError` when the revision is not the post's)
  - `toggle_answered(post: Post) -> None` (raises `ValueError` for a non-question)
  - `thread(session, talk_ref: str) -> list[Post]` (top-level posts, newest first)
  - `talk_stats(session, refs: list[str]) -> dict[str, TalkStats]`; `TalkStats(posts: int, last_activity: datetime)`; talks without posts are absent.

- [ ] **Step 1: Write the failing tests**

`tests/test_discussion_store.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_discussion_store.py -q`
Expected: FAIL with `ModuleNotFoundError: orgestra.discussion.store`.

- [ ] **Step 3: Implement the store**

`src/orgestra/discussion/store.py`:

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_discussion_store.py -q`
Expected: 8 passed. Then `uv run ruff check && uv run ruff format --check && uv run ty check`.

- [ ] **Step 5: Commit**

```bash
git add src/orgestra/discussion/store.py tests/test_discussion_store.py
git commit -m "Add the discussion store: posts, replies, revisions and talk stats"
```

---

### Task 3: Diff and render helpers

**Files:**
- Create: `src/orgestra/discussion/diff.py`, `src/orgestra/discussion/render.py`
- Test: `tests/test_discussion_diff.py`

**Interfaces:**
- Consumes: `Post`, `Revision`, `add_post`, `edit_post`, `session` fixture.
- Produces: `DiffLine(kind: Literal["add","del","same"], text: str)` with property `marker -> str` (`"+"`, `"-"`, `" "`); `line_diff(old: str, new: str) -> list[DiffLine]`; `HistoryEntry(revision: Revision, lines: list[DiffLine])`; `revision_history(post: Post) -> list[HistoryEntry]` (newest first; the oldest revision is all `same` lines); `ago(moment: datetime, now: datetime | None = None) -> str`; `linkify(text: str) -> Markup`.

- [ ] **Step 1: Write the failing tests**

`tests/test_discussion_diff.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_discussion_diff.py -q`
Expected: FAIL with `ModuleNotFoundError: orgestra.discussion.diff`.

- [ ] **Step 3: Implement `diff.py`**

```python
"""Line-based diffs between the revisions of a post."""

from __future__ import annotations

import difflib
from typing import Literal

import attrs

from orgestra.discussion.models import Post, Revision

DiffKind = Literal["add", "del", "same"]
MARKERS: dict[DiffKind, str] = {"add": "+", "del": "-", "same": " "}


@attrs.frozen
class DiffLine:
    kind: DiffKind
    text: str

    @property
    def marker(self) -> str:
        return MARKERS[self.kind]


@attrs.frozen
class HistoryEntry:
    revision: Revision
    lines: list[DiffLine]


def line_diff(old: str, new: str) -> list[DiffLine]:
    kinds: dict[str, DiffKind] = {"+ ": "add", "- ": "del", "  ": "same"}
    return [
        DiffLine(kinds[line[:2]], line[2:])
        for line in difflib.ndiff(old.splitlines(), new.splitlines())
        if line[:2] in kinds
    ]


def revision_history(post: Post) -> list[HistoryEntry]:
    """Every revision with its diff against the one before, newest first; the first is plain text."""
    entries: list[HistoryEntry] = []
    previous: Revision | None = None
    for revision in post.revisions:
        if previous is None:
            lines = [DiffLine("same", text) for text in revision.body.splitlines()]
        else:
            lines = line_diff(previous.body, revision.body)
        entries.append(HistoryEntry(revision, lines))
        previous = revision
    return entries[::-1]
```

- [ ] **Step 4: Implement `render.py`**

```python
"""Template filters for the discussion."""

from __future__ import annotations

import re
from datetime import datetime

from markupsafe import Markup, escape

from orgestra.discussion.models import utc_now

URL = re.compile(r"https?://[^\s<]+")


def ago(moment: datetime, now: datetime | None = None) -> str:
    seconds = ((now or utc_now()) - moment).total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    return f"{int(seconds // 86400)} d ago"


def linkify(text: str) -> Markup:
    """Escape the text, then turn bare http(s) URLs into links. Line breaks are left to CSS."""
    escaped = str(escape(text))
    linked = URL.sub(lambda m: f'<a href="{m[0]}" rel="nofollow noopener">{m[0]}</a>', escaped)
    return Markup(linked)  # noqa: S704 - built from escaped text and links around escaped URLs
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_discussion_diff.py -q && uv run ruff check && uv run ruff format --check && uv run ty check`
Expected: 4 passed, clean. If ruff's rule set does not flag `S704`, drop the `noqa` rather than keep an unused suppression.

- [ ] **Step 6: Commit**

```bash
git add src/orgestra/discussion/diff.py src/orgestra/discussion/render.py tests/test_discussion_diff.py
git commit -m "Add line diffs, revision history and the ago and linkify filters"
```

---

### Task 4: Routes and talk page discussion

**Files:**
- Create: `src/orgestra/discussion/routes.py`, `src/orgestra/templates/partials/discussion/section.html`, `src/orgestra/templates/partials/discussion/post.html`
- Modify: `src/orgestra/app.py` (filters, router, talk route), `src/orgestra/templates/talk.html`, `src/orgestra/static/css/app.css`
- Test: `tests/test_discussion_routes.py`

**Interfaces:**
- Consumes: store functions, `revision_history`, `ago`, `linkify` (Tasks 2 and 3); `request.app.state.services.catalog.talks` (a `dict[str, Talk]` keyed by `year/slug`).
- Produces: `router` (an `APIRouter`) from `orgestra.discussion.routes`; `NAME_COOKIE = "orgestra_name"`; `remembered_name(request) -> str`. Templates get `posts: list[Post]` and `author_name: str` in the talk page context. Markup contract used by the demo: `form.new-post` (fields `kind`, `name`, `body`), `article.post#post-<id>`, `details.reply`, `details.edit`, `details.history`, `form.answered`.

- [ ] **Step 1: Write the failing route tests**

`tests/test_discussion_routes.py`:

```python
import pytest
from fastapi.testclient import TestClient

from orgestra.app import REPO_DATA_DIR, Settings, create_app

TALK = "2025/13-years-of-cryptocurrency-de-anonymization-and-counting"


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(Settings(data_dir=REPO_DATA_DIR, db_path=tmp_path / "test.db")))


def post_to_talk(client, **fields):
    data = {"kind": "comment", "name": "Ada", "body": "Hello"} | fields
    return client.post(f"/talks/{TALK}/posts", data=data, follow_redirects=False)


def test_post_redirects_to_the_talk_and_shows_up_there(client):
    response = post_to_talk(client, kind="question", body="Why does this scale?")

    assert response.status_code == 303
    assert response.headers["location"] == f"/talks/{TALK}#post-1"
    html = client.get(f"/talks/{TALK}").text
    assert "Why does this scale?" in html
    assert "Question" in html


def test_reply_edit_history_restore_and_answered(client):
    post_to_talk(client, kind="question", body="line one\nline two")
    client.post("/posts/1/replies", data={"name": "Bob", "body": "an answer"})
    client.post("/posts/1/edit", data={"name": "Cy", "body": "line one\nline 2"})
    client.post("/posts/1/answered")

    html = client.get(f"/talks/{TALK}").text
    assert "an answer" in html
    assert "(edited)" in html
    assert 'class="diff-del"' in html
    assert "Answered" in html

    client.post("/posts/1/restore/1", data={"name": "Di"})
    restored = client.get(f"/talks/{TALK}").text
    assert restored.count("restore this version") == 2  # three revisions, the newest is current


def test_markup_in_a_body_is_escaped(client):
    post_to_talk(client, body="<script>alert(1)</script> & more")

    html = client.get(f"/talks/{TALK}").text
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; more" in html


@pytest.mark.parametrize("field", ["name", "body"])
def test_blank_fields_are_rejected_and_nothing_is_stored(client, field):
    response = post_to_talk(client, **{field: "   "})

    assert response.status_code == 422
    assert "Hello" not in client.get(f"/talks/{TALK}").text


def test_too_long_fields_are_rejected(client):
    assert post_to_talk(client, name="x" * 41).status_code == 422
    assert post_to_talk(client, body="x" * 5001).status_code == 422


def test_unknown_targets_are_404(client):
    assert client.post("/talks/2025/nope/posts", data={"kind": "comment", "name": "A", "body": "b"}).status_code == 404
    assert client.post("/posts/99/replies", data={"name": "A", "body": "b"}).status_code == 404
    assert client.post("/posts/99/edit", data={"name": "A", "body": "b"}).status_code == 404
    assert client.post("/posts/99/restore/1", data={"name": "A"}).status_code == 404
    assert client.post("/posts/99/answered").status_code == 404
    post_to_talk(client)
    assert client.post("/posts/1/restore/99", data={"name": "A"}).status_code == 404


def test_answered_on_a_comment_is_a_bad_request(client):
    post_to_talk(client)

    assert client.post("/posts/1/answered").status_code == 400


def test_a_non_ascii_name_survives_the_cookie(client):
    post_to_talk(client, name="Zoë Ünal")

    html = client.get(f"/talks/{TALK}").text
    assert 'name="name" value="Zoë Ünal"' in html
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_discussion_routes.py -q`
Expected: FAIL (404 on the new routes, or import errors).

- [ ] **Step 3: Implement the routes**

`src/orgestra/discussion/routes.py`:

```python
"""Form endpoints for the discussion. Every mutation answers 303 back to the talk page."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import quote, unquote

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, StringConstraints
from sqlalchemy.orm import Session

from orgestra.discussion import store
from orgestra.discussion.models import Kind, Post, db

NAME_COOKIE = "orgestra_name"
YEAR = 365 * 24 * 3600

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class NewPost(BaseModel):
    kind: Kind
    name: Name
    body: Body


class Reply(BaseModel):
    name: Name
    body: Body


class Restore(BaseModel):
    name: Name


router = APIRouter()


def remembered_name(request: Request) -> str:
    """The display name the visitor last used; percent-encoded so non-ASCII names survive."""
    return unquote(request.cookies.get(NAME_COOKIE, ""))


def see_post(post: Post, name: str) -> RedirectResponse:
    response = RedirectResponse(f"/talks/{post.talk_ref}#post-{post.id}", status_code=303)
    response.set_cookie(NAME_COOKIE, quote(name), max_age=YEAR, samesite="lax")
    return response


def find_post(session: Session, post_id: int) -> Post:
    post = session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.post("/talks/{year}/{slug}/posts")
def new_post(request: Request, year: int, slug: str, form: Annotated[NewPost, Form()]) -> RedirectResponse:
    ref = f"{year}/{slug}"
    if ref not in request.app.state.services.catalog.talks:
        raise HTTPException(status_code=404, detail="Talk not found")
    with db.begin() as session:
        post = store.add_post(session, ref, form.kind, form.name, form.body)
        return see_post(post, form.name)


@router.post("/posts/{post_id}/replies")
def reply(post_id: int, form: Annotated[Reply, Form()]) -> RedirectResponse:
    with db.begin() as session:
        created = store.add_reply(session, find_post(session, post_id), form.name, form.body)
        return see_post(created, form.name)


@router.post("/posts/{post_id}/edit")
def edit(post_id: int, form: Annotated[Reply, Form()]) -> RedirectResponse:
    with db.begin() as session:
        post = find_post(session, post_id)
        store.edit_post(session, post, form.name, form.body)
        return see_post(post, form.name)


@router.post("/posts/{post_id}/restore/{revision_id}")
def restore(post_id: int, revision_id: int, form: Annotated[Restore, Form()]) -> RedirectResponse:
    with db.begin() as session:
        post = find_post(session, post_id)
        try:
            store.restore_revision(session, post, revision_id, form.name)
        except LookupError as error:
            raise HTTPException(status_code=404, detail="Revision not found") from error
        return see_post(post, form.name)


@router.post("/posts/{post_id}/answered")
def answered(request: Request, post_id: int) -> RedirectResponse:
    with db.begin() as session:
        post = find_post(session, post_id)
        try:
            store.toggle_answered(post)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return see_post(post, remembered_name(request))
```

- [ ] **Step 4: Hook into `app.py`**

Imports: `from orgestra.discussion import routes as discussion_routes`, `from orgestra.discussion.diff import revision_history`, `from orgestra.discussion.render import ago, linkify`, `from orgestra.discussion.store import thread` (and `db` already imported).

In `build_templates`, extend the filters line to:

```python
    templates.env.filters.update(
        hue=persona_hue, initials=initials, summary=summary, ago=ago, linkify=linkify, history=revision_history
    )
```

Replace the `talk` route body's context and return with:

```python
    with db.begin() as session:
        context = {
            "talk": found,
            "questions": services.index.questions_for(found.ref),
            "posts": thread(session, found.ref),
            "author_name": discussion_routes.remembered_name(request),
        }
        return services.templates.TemplateResponse(request, "talk.html", context)
```

In `create_app`, after `app.include_router(router)` add `app.include_router(discussion_routes.router)`.

- [ ] **Step 5: Templates**

In `talk.html`, just before `</article>` add `{% include "partials/discussion/section.html" %}`.

`partials/discussion/section.html`:

```jinja
<section class="discussion" id="discussion">
  <h2>Discussion <span class="count">{{ posts|sum(attribute="thread_size") }}</span></h2>
  <form class="new-post" method="post" action="/talks/{{ talk.ref }}/posts">
    <div class="form-row">
      <select name="kind" aria-label="Type">
        <option value="comment">Comment</option>
        <option value="question">Question</option>
      </select>
      <input name="name" value="{{ author_name }}" placeholder="Your name" maxlength="40" required>
    </div>
    <textarea name="body" rows="3" maxlength="5000" placeholder="Add a comment or ask a question" required></textarea>
    <button class="button" type="submit">Post</button>
  </form>
  {% for post in posts %}
    {% include "partials/discussion/post.html" %}
  {% else %}
    <p class="muted">No discussion yet. Ask the first question.</p>
  {% endfor %}
</section>
```

`partials/discussion/post.html`:

```jinja
<article class="post{% if post.kind == 'question' %} post-question{% endif %}" id="post-{{ post.id }}">
  <details class="thread" open>
    <summary class="post-head">
      <span class="avatar small" style="--hue: {{ post.author_name|hue }}" aria-hidden="true">{{ post.author_name|initials }}</span>
      <strong>{{ post.author_name }}</strong>
      {% if post.kind == "question" %}
        <span class="badge">Question</span>
        {% if post.answered %}<span class="badge badge-answered">Answered</span>{% endif %}
      {% endif %}
      <span class="muted" title="{{ post.created_at }} UTC">{{ post.created_at|ago }}</span>
    </summary>
    <div class="post-body">{{ post.body|linkify }}</div>
    <div class="post-actions">
      <details class="reply">
        <summary>reply</summary>
        <form method="post" action="/posts/{{ post.id }}/replies">
          <input name="name" value="{{ author_name }}" placeholder="Your name" maxlength="40" required>
          <textarea name="body" rows="2" maxlength="5000" required></textarea>
          <button class="button" type="submit">Reply</button>
        </form>
      </details>
      <details class="edit">
        <summary>edit</summary>
        <form method="post" action="/posts/{{ post.id }}/edit">
          <input name="name" value="{{ author_name }}" placeholder="Your name" maxlength="40" required>
          <textarea name="body" rows="3" maxlength="5000" required>{{ post.body }}</textarea>
          <button class="button" type="submit">Save</button>
        </form>
      </details>
      {% if post.kind == "question" %}
        <form class="answered inline" method="post" action="/posts/{{ post.id }}/answered">
          <button class="link-button" type="submit">{{ "mark unanswered" if post.answered else "mark answered" }}</button>
        </form>
      {% endif %}
      {% if post.edited %}
        <details class="history">
          <summary>(edited)</summary>
          <ol class="revisions">
            {% for entry in post|history %}
              <li>
                <div class="revision-head">
                  <strong>{{ entry.revision.editor_name }}</strong>
                  <span class="muted">{{ entry.revision.created_at|ago }}</span>
                  {% if not loop.first %}
                    <form class="inline" method="post" action="/posts/{{ post.id }}/restore/{{ entry.revision.id }}">
                      <input type="hidden" name="name" value="{{ author_name or 'Anonymous' }}">
                      <button class="link-button" type="submit">restore this version</button>
                    </form>
                  {% endif %}
                </div>
                <pre class="diff">{% for line in entry.lines %}<span class="diff-{{ line.kind }}">{{ line.marker }} {{ line.text }}</span>{% endfor %}</pre>
              </li>
            {% endfor %}
          </ol>
        </details>
      {% endif %}
    </div>
    {% for reply in post.replies %}
      {% with post=reply %}
        {% include "partials/discussion/post.html" %}
      {% endwith %}
    {% endfor %}
  </details>
</article>
```

- [ ] **Step 6: Styles**

Append to `app.css` (before the `@media (max-width: 1000px)` block):

```css
/* Discussion */
.discussion { margin-top: 2.5rem; border-top: 1px solid var(--border); padding-top: 0.5rem; }
.new-post { display: grid; gap: 0.5rem; margin: 0 0 1.5rem; }
.discussion input, .discussion select, .discussion textarea {
  font: inherit;
  color: var(--text);
  background: var(--box);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.4rem 0.6rem;
}
.discussion textarea { width: 100%; resize: vertical; }
.form-row { display: flex; gap: 0.5rem; }
.form-row input { flex: 1; }
.new-post .button, .discussion form .button { justify-self: start; margin: 0; }
.post { margin: 0.75rem 0; }
.post .post { margin-left: 1rem; padding-left: 0.75rem; border-left: 2px solid var(--border); }
.post-head { display: flex; align-items: center; gap: 0.5rem; cursor: pointer; list-style-position: outside; }
.post-body { margin: 0.35rem 0 0.25rem; white-space: pre-wrap; overflow-wrap: anywhere; }
.post-actions { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.25rem 1rem; font-size: 13px; color: var(--faint); }
.post-actions summary, .link-button { cursor: pointer; color: var(--faint); background: none; border: 0; padding: 0; font: inherit; }
.post-actions summary:hover, .link-button:hover { color: var(--link); text-decoration: underline; }
.post-actions details[open] { flex-basis: 100%; }
.post-actions details form { display: grid; gap: 0.4rem; margin: 0.4rem 0; }
.inline { display: inline; }
.badge {
  font-size: 11px;
  padding: 0 0.5rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  color: var(--muted);
}
.badge-answered { border-color: var(--green); color: var(--green); }
.revisions { list-style: none; margin: 0.4rem 0; padding: 0; color: var(--text); }
.revision-head { display: flex; gap: 0.75rem; align-items: baseline; }
.diff { margin: 0.25rem 0 0.75rem; padding: 0.4rem 0; background: var(--chip); border-radius: 6px; font-size: 12px; overflow-x: auto; }
.diff span { display: block; padding: 0 0.6rem; white-space: pre-wrap; }
.diff-add { background: rgb(52 168 83 / 0.2); }
.diff-del { background: rgb(234 67 53 / 0.2); }
.diff-same { color: var(--faint); }
```

- [ ] **Step 7: Run to verify it passes**

Run: `uv run pytest -q && uv run ruff check && uv run ruff format --check && uv run ty check`
Expected: all pass. Fix line-length failures in the test file by wrapping, not by relaxing the config.

- [ ] **Step 8: Commit**

```bash
git add src tests
git commit -m "Add the talk discussion: nested posts, edits with history and restore"
```

---

### Task 5: Forum-style search results

**Files:**
- Modify: `src/orgestra/app.py` (`search_response`), `src/orgestra/templates/partials/results.html`, `src/orgestra/static/css/app.css`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `talk_stats` (Task 2), `TalkStats`.
- Produces: `results.html` receives `stats: dict[str, TalkStats]` next to `result`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_app.py`:

```python
def test_results_list_shows_post_counts_and_activity(client):
    ref = "2025/13-years-of-cryptocurrency-de-anonymization-and-counting"
    client.post(f"/talks/{ref}/posts", data={"kind": "comment", "name": "Ada", "body": "Nice talk"})

    html = client.get("/search", params={"q": "cryptocurrency"}).text

    assert 'class="topics-head"' in html
    assert '<span class="hit-replies" title="Posts in the discussion">1</span>' in html
    assert "just now" in html
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_app.py::test_results_list_shows_post_counts_and_activity -q`
Expected: FAIL (`topics-head` missing).

- [ ] **Step 3: Pass stats in `search_response`**

Imports: `from orgestra.discussion.store import talk_stats, thread` (extend the existing `thread` import). Replace the function:

```python
def search_response(request: Request, services: Services, query: str) -> HTMLResponse:
    result = services.index.search(query) if query.strip() else None
    if result is None:
        return services.templates.TemplateResponse(request, "home.html", {"result": None})
    with db.begin() as session:
        stats = talk_stats(session, [hit.talk.ref for hit in result.hits])
        context = {"result": result, "stats": stats}
        if not is_fragment_request(request):
            return services.templates.TemplateResponse(request, "search.html", context)
        response = services.templates.TemplateResponse(request, "partials/results.html", context)
    speakers = list(dict.fromkeys(s.slug for hit in result.hits for s in hit.talk.speakers))
    response.headers["HX-Trigger"] = hx_trigger(SPOTLIGHT, Spotlight(speakers=speakers))
    return response
```

- [ ] **Step 4: Rework `results.html` rows**

Replace the `{% for hit in result.hits %}` article block (keep the "People also ask" block and the `{% else %}` empty message exactly as they are) with:

```jinja
  {% if result.hits %}
    <div class="topics-head" aria-hidden="true">
      <span>Talk</span><span>Posts</span><span>Activity</span>
    </div>
  {% endif %}
  {% for hit in result.hits %}
    {% set talk_stats = stats.get(hit.talk.ref) %}
    <article class="hit{% if not hit.talk.extracted %} hit-pending{% endif %}">
      <div class="hit-main">
        <div class="hit-source">
          {% for person in hit.talk.speakers[:3] %}
            <span class="avatar small" style="--hue: {{ person.slug|hue }}" aria-hidden="true">{{ person.name|initials }}</span>
          {% else %}
            <span class="avatar small" aria-hidden="true">?</span>
          {% endfor %}
          <div>
            <span class="hit-site">{{ hit.talk.speakers|map(attribute="name")|join(", ") or hit.talk.organization|upper }}</span>
            <span class="hit-crumbs">{{ hit.talk.organization }} › {{ hit.talk.year }} › {{ hit.talk.section or "talk" }}</span>
          </div>
        </div>
        <h3>
          <a href="/talks/{{ hit.talk.ref }}">{{ hit.talk.display_title }}</a>
          <span class="badge">{{ hit.talk.year }}</span>
        </h3>
        <p class="hit-snippet">
          {% if hit.talk.day %}<span class="muted">{{ hit.talk.day }} {{ hit.talk.start }} —</span>{% endif %}
          {{ (hit.talk.abstract or "Details of this talk have not been extracted yet.")|summary }}
        </p>
        {% if hit.talk.tags %}
          <p class="hit-tags">
            {% for tag in hit.talk.tags %}<span class="tag">{{ tag }}</span>{% endfor %}
          </p>
        {% endif %}
      </div>
      <span class="hit-replies" title="Posts in the discussion">{{ talk_stats.posts if talk_stats else 0 }}</span>
      <span class="hit-activity muted">{{ talk_stats.last_activity|ago if talk_stats else "—" }}</span>
    </article>
```

The `{% if loop.index == 2 and result.top_questions() %}` block stays directly after the `</article>`, unchanged.

- [ ] **Step 5: Styles**

In `app.css`, change `.results { max-width: 652px; }` to `.results { max-width: 900px; }` and add after the `.hit` rules:

```css
.topics-head, .hit { display: grid; grid-template-columns: minmax(0, 1fr) 4rem 6rem; gap: 0 1rem; }
.topics-head { color: var(--faint); font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; padding-bottom: 0.4rem; border-bottom: 1px solid var(--border); margin-bottom: 1rem; }
.hit { padding-bottom: 1.25rem; border-bottom: 1px solid var(--border); align-items: start; }
.hit-source .avatar + .avatar { margin-left: -0.5rem; }
.hit-replies { text-align: center; color: var(--muted); font-size: 16px; padding-top: 0.5rem; }
.hit-activity { font-size: 13px; padding-top: 0.6rem; }
.hit h3 .badge { margin-left: 0.5rem; vertical-align: middle; }
```
and add inside the existing `@media (max-width: 600px)` block: `.topics-head, .hit { grid-template-columns: minmax(0, 1fr) 3rem; } .hit-activity, .topics-head span:last-child { display: none; }`.

- [ ] **Step 6: Run to verify it passes**

Run: `uv run pytest -q && uv run ruff check && uv run ruff format --check && uv run ty check`
Expected: all pass, including the existing search fragment and `People also ask` tests.

- [ ] **Step 7: Commit**

```bash
git add src tests
git commit -m "Show posts and activity in a forum-style result list"
```

---

### Task 6: Demo step and docs

**Files:**
- Modify: `frontend/scripts/record-demo.mjs`, `README.md`, `CLAUDE.md`

**Interfaces:**
- Consumes: the markup contract from Task 4.

- [ ] **Step 1: Add the discussion step to the tour**

In `record-demo.mjs`, add above `tour`:

```js
/** Discussion: ask a question, reply, correct the question and open its history. */
async function discuss(page) {
  const form = page.locator("form.new-post");
  await form.scrollIntoViewIfNeeded();
  await form.locator("select[name=kind]").selectOption("question");
  await form.locator("input[name=name]").fill("Ada");
  await form.locator("textarea[name=body]").pressSequentially("How does this hold up at scale?", { delay: 50 });
  await form.locator("button[type=submit]").click();
  await page.waitForSelector(".post");
  log("question posted");
  await pause(page, 1500);
  const post = page.locator(".post").first();
  await post.locator("details.reply > summary").click();
  await post.locator("details.reply input[name=name]").fill("Grace");
  await post.locator("details.reply textarea").pressSequentially("Mostly by sharding early.", { delay: 50 });
  await post.locator("details.reply button[type=submit]").click();
  await page.waitForSelector(".post .post");
  log("reply posted");
  await pause(page, 1500);
  await post.locator("details.edit > summary").first().click();
  await post.locator("details.edit textarea").first().pressSequentially(" (asking about 10k users)", { delay: 50 });
  await post.locator("details.edit button[type=submit]").first().click();
  await page.waitForSelector("details.history");
  log("edited");
  await pause(page, 1000);
  await page.locator("details.history > summary").first().click();
  log("history");
  await pause(page, 3500);
}
```

and in `tour`, right after the first `log("talk"); await pause(page, 3000);` pair add `await discuss(page);`.

- [ ] **Step 2: Document it**

In `README.md` add to the settings paragraph: `ORGESTRA_DB_PATH` (SQLite file for the discussion, default `data/orgestra.db`). In `CLAUDE.md` step 2 of the demo list, change `uv run orgestra` to `ORGESTRA_DB_PATH=$(mktemp -d)/demo.db uv run orgestra` so the demo does not write to the real discussion database.

- [ ] **Step 3: Check the script parses**

Run: `cd frontend && node --check scripts/record-demo.mjs && npm run check`
Expected: no output from `node --check`; `npm run check` passes.

- [ ] **Step 4: Commit**

```bash
git add frontend/scripts/record-demo.mjs README.md CLAUDE.md
git commit -m "Show the discussion in the demo tour and document the database setting"
```

---

### Task 7: Full checks, demo video and PR

**Files:** none (verification and delivery).

- [ ] **Step 1: Run every check**

Run: `just check` (or, without `just`: `uv run pytest && uv run ruff check && uv run ruff format --check && uv run ty check`, then `cd frontend && npm run check && npm test && npm run build`).
Expected: all green. Fix any failure with a new commit.

- [ ] **Step 2: Run the app against a throwaway database and record the demo**

```bash
cd frontend && npm ci && npm run build && cd ..
ORGESTRA_DB_PATH=$(mktemp -d)/demo.db uv run orgestra &   # note the PID, stop it after recording
cd frontend && npm run demo -- --out ../demo.mp4          # CHROMIUM_PATH if Playwright's browser is missing
```
Expected: `demo.mp4` in the repo root showing home, search results as a topic list, a talk, a posted question, a reply, an edit and the open history. Do not commit it. Stop the background server.

- [ ] **Step 3: Open the pull request**

Load the `git-style` skill, then check the forge with `git remote get-url origin` and `gh pr view` (an open PR for `claude/app-scaffold-bwfu17` may already exist; if so push to it and update its body). Push the branch (no force) and create or update the PR with a prose body: the problem (no way to discuss talks), the behavior (nested comments and questions, open editing with line-diff history, forum-style results), and implementation notes (alchemical on SQLite at `ORGESTRA_DB_PATH`, form posts with `<details>`, no htmx fragments). Then load `pr-checks` and follow it.

- [ ] **Step 4: Attach the video**

Share `demo.mp4` where the reviewer reads it (CLAUDE.md). GitHub has no CLI or API for attaching a video to a comment: ask the user to drag `demo.mp4` into the PR conversation, or, if they prefer, upload it somewhere they name. Do not publish it to an external service without asking.

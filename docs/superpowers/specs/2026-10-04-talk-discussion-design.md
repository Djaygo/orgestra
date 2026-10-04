# Talk discussion: comments, questions and revisions

## Goal

Visitors read a talk and discuss it: they add comments and questions, reply in a tree (Reddit or
Hacker News style), and anyone can correct any post, with earlier versions kept and viewable as
line diffs. Search results and the talk page take on the look of a Discourse forum
(governance.aave.com): a topic-list style result and a thread style discussion.

## Decisions

- **Anonymous posting.** A visitor types a display name and a message; no accounts. The name is
  remembered in a cookie.
- **No moderation.** No admin role, no hide or delete. Open editing with restorable history is the
  safeguard.
- **Anyone can edit any post.** Every edit appends a revision attributed to the editor's display name.
- **Style scope.** Search results and the talk page only. The home page stays as it is.
- **Storage.** SQLite through [alchemical](https://github.com/miguelgrinberg/alchemical), a thin
  SQLAlchemy 2.0 wrapper (`Alchemical(url)`, `db.Model`, `db.create_all()`, `with db.begin() as session`).
  Added with `uv add alchemical`.
- **Scale.** Few users and no bots are assumed: no spam protection and no edit-conflict handling.
  Concurrent edits are last write wins; every edit is a kept revision, so nothing is lost.

## Data model

SQLAlchemy 2.0 models on `db.Model`:

```python
class Post(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    talk_ref: Mapped[str] = mapped_column(index=True)  # "<year>/<slug>", the catalog key
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("post.id"))  # None for a top-level post
    kind: Mapped[str]  # "comment" | "question"
    author_name: Mapped[str]
    created_at: Mapped[datetime]  # UTC
    answered: Mapped[bool] = mapped_column(default=False)  # questions only
    revisions: Mapped[list[Revision]] = relationship(order_by="Revision.id")
    replies: Mapped[list[Post]] = relationship(order_by="Post.id")


class Revision(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("post.id"))
    body: Mapped[str]
    editor_name: Mapped[str]
    created_at: Mapped[datetime]
```

- The current text of a post is its latest revision; the first revision is the original post. The
  post row holds no copy of the body.
- Edit count, "edited" state and reply counts are derived by query, never stored.
- Only top-level posts have a kind chosen by the visitor; replies are always `comment`.
- `answered` is the only mutable column on `post`. Anyone can toggle it on a question.
- The talks themselves stay in the JSON dataset; the database holds discussion data only.
- Tables are created on startup with `db.create_all()`. `ORGESTRA_DB_PATH` sets the file (default
  `data/orgestra.db`, gitignored); tests use a file under `tmp_path` (an in-memory SQLite database is per thread, and sync routes run
  in a thread pool).

## Behaviour

### Talk page

Talk content first (as today), then a "Discussion" section: the new-post form (kind selector
Comment or Question, name, body), then the thread.

- Posts are nested by `parent_id`, indented, each with a collapse toggle, author, relative time and
  a "reply" link. Top-level posts are ordered newest first, replies oldest first.
- A kind badge marks questions; answered questions show an "answered" badge and the toggle.
- No htmx fragments and no client-side code: "reply", "edit" and "(edited)" are `<details>` elements
  that expand inline, and every mutation is a plain form POST answered with a 303 back to the talk
  page. The existing `hx-boost` turns those into in-place page swaps.

### Editing and history

- Every post has an "edit" link expanding a form pre-filled with the current text. Saving appends a
  revision with the editor's name; the original author is not checked. Saving unchanged text adds
  nothing.
- A post with more than one revision shows a small "(edited)" link next to its actions. It expands
  the post's history inline.
- The history lists revisions newest first with editor and time. Each revision is a line-based diff
  against the previous one (stdlib `difflib`): added lines green, removed lines red, unchanged lines
  muted. The first revision is shown as plain text.
- Each non-current revision has a "restore this version" button that appends a new revision with
  that revision's text. Nothing is ever deleted.

### Input limits

- Body: plain text, 1 to 5000 characters after trimming. Name: 1 to 40 characters. The forms carry
  `required` and `maxlength`; the server enforces the same limits and answers 422, storing nothing.
- The remembered display name is a percent-encoded cookie, so non-ASCII names survive the round trip.
- Output is HTML-escaped by Jinja. Line breaks are kept (CSS `white-space: pre-wrap`) and bare
  `http(s)` URLs become links with `rel="nofollow noopener"`.
- Unknown talk or post ids return 404. A reply takes its talk from its parent, so it cannot cross talks.

### Style

- Search results (`partials/results.html`) become a forum topic list: one row per talk with title,
  year or section badge, speaker avatars, reply count and last activity. Reply count and last
  activity come from the database, derived per request for the hits shown.
- The talk page and discussion use the same visual language: compact rows, badges, avatars, thread
  indentation.
- The existing CSS tokens and their light and dark values are reused; only layout and component
  styles are added. This is a close, not pixel-exact, match to Aave.

## Components

| Unit | Responsibility | Depends on |
|---|---|---|
| `discussion/models.py` | `db` (Alchemical), `Post`, `Revision` | alchemical, settings |
| `discussion/store.py` | create post, add revision, restore, toggle answered, list thread, counts; takes a session | `models` |
| `discussion/diff.py` | line diff of two texts, revision history of a post | `difflib`, `models` |
| `discussion/render.py` | template filters: relative time, linkified text | `markupsafe` |
| `discussion/routes.py` | form endpoints, validation, remembered-name cookie | `store` |
| templates `partials/discussion/*` | thread, post, forms, history | route contexts |
| `results.html`, `talk.html`, `app.css` | forum-style list and talk page | `store` for counts |

Boundaries: `store` functions take a session and work on `Post` and `Revision`; they know nothing
about HTTP. Routes open one `db.begin()` transaction per request and render before it closes. Routes parse and validate input at the edge. Templates only render.

## Routes

All mutations answer 303 to `/talks/{year}/{slug}#post-{id}` and set the remembered-name cookie.

| Method and path | Result |
|---|---|
| `POST /talks/{year}/{slug}/posts` | create a top-level post (kind, name, body) |
| `POST /posts/{id}/replies` | reply to a post (name, body) |
| `POST /posts/{id}/edit` | append a revision (name, body) |
| `POST /posts/{id}/restore/{revision_id}` | append a revision with that text (name) |
| `POST /posts/{id}/answered` | toggle answered on a question |

## Testing

- `store` on an in-memory SQLite: nesting, ordering, latest revision, edit count, restore.
- `diff`: added, removed, unchanged and first-revision cases.
- Routes through `TestClient`: post, reply, edit, restore, answered; validation errors,
  HTML escaping, 404s, cross-talk parent rejection.
- Extend `tests/test_app.py` for the talk page and results list rendering counts.
- Frontend demo (`frontend/scripts/record-demo.mjs`) gains a step: open a talk, post a comment, edit
  it, open the history.

## Out of scope

Accounts, moderation, spam protection, edit-conflict handling, notifications, search over comments, pagination of very long threads, rich
text, and any change to the home page.

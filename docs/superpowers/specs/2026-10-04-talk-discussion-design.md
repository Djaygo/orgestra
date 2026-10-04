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
- **Storage.** SQLite through stdlib `sqlite3`, one file. No ORM, no new dependency.

## Data model

```sql
posts(
  id          INTEGER PRIMARY KEY,
  talk_ref    TEXT NOT NULL,                 -- "<year>/<slug>", the catalog key
  parent_id   INTEGER REFERENCES posts(id),  -- NULL for a top-level post
  kind        TEXT NOT NULL CHECK (kind IN ('comment', 'question')),
  author_name TEXT NOT NULL,
  created_at  TEXT NOT NULL,                 -- UTC ISO 8601
  answered    INTEGER NOT NULL DEFAULT 0     -- questions only
)
revisions(
  id          INTEGER PRIMARY KEY,
  post_id     INTEGER NOT NULL REFERENCES posts(id),
  body        TEXT NOT NULL,
  editor_name TEXT NOT NULL,
  created_at  TEXT NOT NULL
)
```

- The current text of a post is its latest revision; the first revision is the original post. The
  post row holds no copy of the body.
- Edit count, "edited" state and reply counts are derived by query, never stored.
- Only top-level posts have a kind chosen by the visitor; replies are always `comment`.
- `answered` is the only mutable column on `posts`. Anyone can toggle it on a question.
- The talks themselves stay in the JSON dataset; the database holds discussion data only.
- The schema is created on startup (`CREATE TABLE IF NOT EXISTS`). `ORGESTRA_DB_PATH` sets the file
  (default `data/orgestra.db`); the file is gitignored.

## Behaviour

### Talk page

Talk content first (as today), then a "Discussion" section: the new-post form (kind selector
Comment or Question, name, body), then the thread.

- Posts are nested by `parent_id`, indented, each with a collapse toggle, author, relative time and
  a "reply" link. Top-level posts are ordered newest first, replies oldest first.
- A kind badge marks questions; answered questions show an "answered" badge and the toggle.
- Reply and edit forms open inline through htmx; saving swaps the affected post (or subtree) in place.
  Without JavaScript the same routes work as full-page form posts.

### Editing and history

- Every post has an "edit" link opening an inline form pre-filled with the current text. Saving
  appends a revision with the editor's name; the original author is not checked.
- A post with more than one revision shows a small "(edited)" hyperlink next to its timestamp. It
  opens the history panel for that post.
- The history lists revisions newest first with editor and time. Each revision is a line-based diff
  against the previous one (stdlib `difflib`): added lines green, removed lines red, unchanged lines
  muted. The first revision is shown as plain text.
- Each non-current revision has a "restore this version" button that appends a new revision with
  that revision's text. Nothing is ever deleted.
- Simultaneous edits: the edit form carries the id of the revision it started from. If the latest
  revision differs on save, nothing is written; the form is shown again with the newer text and a
  notice, so no edit is lost silently.

### Input and abuse limits

- Body: plain text, 1 to 5000 characters after trimming. Name: 1 to 40 characters. Violations
  re-render the form with an error; nothing is stored.
- Output is HTML-escaped by Jinja. Line breaks are kept and bare `http(s)` URLs become links with
  `rel="nofollow noopener"`.
- A hidden honeypot field rejects naive bots silently.
- A per-client limit on creating and editing posts (in memory, per IP, for example 10 per minute)
  returns 429.
- Unknown `talk_ref` or `parent_id` returns 404; a reply must belong to the same talk as its parent.

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
| `discussion/db.py` | open the SQLite file, create the schema | `sqlite3`, settings |
| `discussion/store.py` | create post, add revision, restore, toggle answered, list thread, counts | `db` |
| `discussion/diff.py` | line diff of two texts into renderable lines | `difflib` |
| `discussion/routes.py` | htmx and form endpoints, validation, rate limit | `store`, `diff`, templates |
| templates `partials/discussion/*` | thread, post, forms, history panel | route contexts |
| `results.html`, `talk.html`, `app.css` | forum-style list and talk page | `store` for counts |

Boundaries: `store` takes and returns attrs records (`Post`, `Revision`); it knows nothing about
HTTP. Routes parse and validate input at the edge. Templates only render.

## Routes

| Method and path | Result |
|---|---|
| `POST /talks/{year}/{slug}/posts` | create a top-level post or, with `parent_id`, a reply |
| `GET /posts/{id}/edit` | inline edit form |
| `POST /posts/{id}/edit` | append a revision, or the conflict form |
| `GET /posts/{id}/history` | history panel with diffs |
| `POST /posts/{id}/restore/{revision_id}` | append a revision with that text |
| `POST /posts/{id}/answered` | toggle answered on a question |

htmx requests return the affected fragment; plain requests redirect back to the talk page.

## Testing

- `store` on an in-memory SQLite: nesting, ordering, latest revision, edit count, restore,
  conflict detection.
- `diff`: added, removed, unchanged and first-revision cases.
- Routes through `TestClient`: post, reply, edit, history, restore, answered; validation errors,
  HTML escaping, honeypot, rate limit, 404s, cross-talk parent rejection.
- Extend `tests/test_app.py` for the talk page and results list rendering counts.
- Frontend demo (`frontend/scripts/record-demo.mjs`) gains a step: open a talk, post a comment, edit
  it, open the history.

## Out of scope

Accounts, moderation, notifications, search over comments, pagination of very long threads, rich
text, and any change to the home page.

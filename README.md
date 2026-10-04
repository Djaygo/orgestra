# Orgestra

Search and personas over the talks and slides of a conference (GOTO Copenhagen to start with).

- **Search**: one search bar; questions are extracted from every talk, and the query is expanded with
  a thesaurus and typo correction, so "llm agnts" also finds "large language model" and "agents".
- **Sources**: a sidebar indexes every edition, talk and speaker.
- **Personas**: each speaker has a page with role, links and contact details (email when public).
- **Stage**: the speakers walk around a three.js plaza and talk to each other about their talks.

## Run it

```sh
uv sync          # Python 3.11+, uv
just build       # optional: builds the three.js stage
just run         # http://127.0.0.1:8000
just dev         # develop: builds the stage, runs the backend (reload) and the stage watcher, opens the browser
```

`just` lists every recipe; each one wraps the plain `uv` and `npm` commands in the `justfile`.

Without the frontend build the app still works; the stage shows the conversation transcript only.

Settings (environment): `ORGESTRA_DATA_DIR` (default `data/`), `ORGESTRA_TURN_INTERVAL` (seconds
between conversation turns, default 3.5), `ORGESTRA_DB_PATH` (SQLite file for the talk discussion, default `data/orgestra.db`), `ORGESTRA_ISSUES_PROVIDER` (`github`), `ORGESTRA_ISSUES_REPO` (`owner/name`) and `ORGESTRA_ISSUES_TOKEN` (a fine-grained token with Issues read and write on that repository; the "Report a bug" button files an issue there and is hidden unless both repo and token are set), `ORGESTRA_HOST`, `ORGESTRA_PORT`, `ORGESTRA_RELOAD`.

## Checks

```sh
just check
```

## Demo video

With the app running, `just demo` records a short tour
(home, a search, People also ask, a talk, a speaker) with Playwright. `.mp4` needs ffmpeg; `.webm`
does not. Agents attach one to every pull request that changes the frontend (see CLAUDE.md).

## How it fits together

HTMX pages plus one three.js island:

| Part | Where | Notes |
|---|---|---|
| Dataset | `data/<organization>/` | talk and speaker JSON, see `data/gotocph/README.md` |
| Loading | `src/orgestra/dataset.py` | pydantic models at the edge, one in-memory `Catalog` |
| Questions | `src/orgestra/questions.py` | from the abstract today, slide text once decks are downloaded |
| Search | `search.py`, `thesaurus.py`, `resources/thesaurus.toml` | weighted fields, synonym groups, rapidfuzz typo fixes |
| Conversations | `conversations.py` | the server decides who says what and streams turns over SSE |
| Routes | `app.py` | full pages for navigation, fragments for htmx, `/conversations/stream` for SSE |
| Templates | `src/orgestra/templates/` | Jinja2; htmx and its SSE extension are vendored in `static/vendor/` |
| Stage | `frontend/src/` | TypeScript + Vite, built into `src/orgestra/static/dist/` |

The pages follow Google search: a centred logo and search box on the home page, and on the results
page a search box that updates `#results` while typing (`hx-get`, debounced, `hx-push-url`), with a
"People also ask" box. Links and forms are boosted into `#main`. The stage is a fixed, transparent,
full-width strip along the bottom: page content fades out underneath it, and it sits outside every
swap target with `hx-preserve`, so it keeps its WebGL context across navigation.

Server and stage talk only through DOM events, defined in `src/orgestra/events.py` and
`frontend/src/events.ts`:

- `character:spotlight` `{speakers: string[]}`: sent in the `HX-Trigger` header of a search result;
  the matching speakers' characters hop and show their names.
- `character:say` `{speaker, listener, text}`: each SSE `turn` swaps in the transcript; the newest
  line carries `data-say-*` attributes, which the stage turns into this event, and the speaker walks
  up to the listener with a speech bubble.

`stage.js` is 2 kB; three.js (about 135 kB gzipped) loads as a separate chunk only once the stage is on
screen.

# Orgestra

Python backend (FastAPI, Jinja2, htmx) in `src/orgestra`, three.js stage in `frontend/`. See README.md.

## Checks before pushing
- `just check` (Python: pytest, ruff check, ruff format --check, ty; frontend: check, test, build)

## Demo video for frontend changes
When a change touches templates, CSS or `frontend/`, record a short video of it and share it with
the pull request:

1. `cd frontend && npm ci && npm run build`
2. `uv run orgestra` (from the repo root, in the background)
3. `cd frontend && npm run demo -- --out ../demo.mp4` (`--query` changes the search it types;
   set `CHROMIUM_PATH` when Playwright's own browser is not installed)
4. Attach the video where the reviewer reads it (the PR thread or project chat). Do not commit it.

Extend the tour in `frontend/scripts/record-demo.mjs` when a new page or interaction should be shown.
